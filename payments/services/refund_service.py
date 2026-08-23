import requests

from django.db import transaction
from django.utils import timezone

from audit.models import AuditLog
from events.models.ticket_type import TicketType
from orders.models import Order
from payments.models import Payment, Refund
from payments.services.paymob_service import PaymobService


class TransientProviderError(Exception):
    """Provider unreachable (network/timeout/5xx) — safe to retry."""


class PermanentProviderError(Exception):
    """Provider rejected the refund (4xx) — retrying will not help."""


@transaction.atomic
def process_order_refund(*, user, order_id, reason):
    # ---------------------------------
    # 1. Lock order and validate (short tx)
    # ---------------------------------

    order = (
        Order.objects.select_for_update(of=("self",))
        .select_related(
            "payment",
            "reservation",
            "reservation__ticket_type",
            "reservation__ticket_type__event",
        )
        .get(id=order_id)
    )

    is_buyer = order.user_id == user.id
    is_organizer = order.reservation.ticket_type.event.organizer_id == user.id

    if not (user.is_staff or is_buyer or is_organizer):
        raise PermissionError("You do not have permission to refund this order.")

    if order.status != Order.OrderStatus.PAID:
        raise ValueError("Only paid orders can be refunded.")

    if getattr(order, "refund", None) is not None:
        raise ValueError("Order has already been refunded.")

    if (
        order.payment is None
        or order.payment.status != Payment.PaymentStatus.SUCCESS
    ):
        raise ValueError("Order does not have a successful payment to refund.")

    # ---------------------------------
    # 2. Record refund intent as PENDING and release locks.
    #    The Paymob call happens in a background worker,
    #    never inside this transaction or the HTTP request.
    # ---------------------------------

    refund = Refund.objects.create(
        order=order,
        reason=reason,
        status=Refund.RefundStatus.PENDING,
    )

    def _enqueue():
        from payments.tasks import process_refund_task

        process_refund_task.delay(refund.id)

    transaction.on_commit(_enqueue)

    return refund


def finalize_refund(*, refund_id):
    # ---------------------------------
    # 1. Lock and snapshot context (short tx)
    # ---------------------------------

    context = _prepare_refund_finalization(refund_id=refund_id)

    if context is None:
        return None

    # ---------------------------------
    # 2. Call Paymob with NO transaction or locks held
    # ---------------------------------

    paymob = PaymobService()

    try:
        paymob.create_refund(**context["paymob_kwargs"])
    except requests.HTTPError as exc:
        mark_refund_failed(
            refund_id=refund_id,
            detail=f"Provider rejected refund ({exc.response.status_code}).",
        )
        raise PermanentProviderError(str(exc)) from exc
    except requests.RequestException as exc:
        raise TransientProviderError(str(exc)) from exc

    # ---------------------------------
    # 3. Finalize locally in a fresh short tx
    # ---------------------------------

    return _complete_refund(context=context)


def _prepare_refund_finalization(*, refund_id):
    # NOTE: Order.payment is nullable, so it must NOT be joined under
    # select_for_update (Postgres forbids locking the nullable side of
    # an outer join). It is read separately below; the completing tx
    # re-validates everything under lock before mutating anything.
    refund = (
        Refund.objects.select_for_update()
        .select_related(
            "order",
            "order__reservation",
        )
        .get(id=refund_id)
    )

    if refund.status != Refund.RefundStatus.PENDING:
        return None

    order = refund.order

    if order.status != Order.OrderStatus.PAID:
        mark_refund_failed(
            refund_id=refund_id,
            detail="Order is no longer paid; refund aborted.",
        )
        return None

    payment = order.payment

    if payment is None or payment.provider_transaction_id is None:
        mark_refund_failed(
            refund_id=refund_id,
            detail="Payment has no provider transaction to refund.",
        )
        return None

    return {
        "refund_id": refund.id,
        "order_id": order.id,
        "paymob_kwargs": {
            "transaction_id": payment.provider_transaction_id,
            "amount_cents": payment.amount,
            "description": refund.reason,
        },
    }


def _complete_refund(*, context):
    refund = (
        Refund.objects.select_for_update()
        .select_related("order")
        .get(id=context["refund_id"])
    )

    if refund.status != Refund.RefundStatus.PENDING:
        return refund

    order = (
        Order.objects.select_for_update(of=("self",))
        .select_related(
            "payment",
            "reservation",
            "reservation__ticket_type",
        )
        .get(id=context["order_id"])
    )

    if order.status != Order.OrderStatus.PAID:
        mark_refund_failed(
            refund_id=refund.id,
            detail="Order status changed during refund; refund aborted.",
        )
        return refund

    ticket_type = TicketType.objects.select_for_update().get(
        id=order.reservation.ticket_type_id
    )

    previous_inventory = ticket_type.available_inventory

    ticket_type.available_inventory += order.quantity

    ticket_type.save(
        update_fields=[
            "available_inventory",
            "updated_at",
        ]
    )

    order.payment.status = Payment.PaymentStatus.REFUNDED

    order.payment.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    order.status = Order.OrderStatus.REFUNDED

    order.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    refund.status = Refund.RefundStatus.SUCCESS
    refund.refunded_at = timezone.now()

    refund.save(
        update_fields=[
            "status",
            "refunded_at",
            "updated_at",
        ]
    )

    earning = getattr(order, "earning", None)

    if earning:
        earning.gross_amount = 0
        earning.platform_fee = 0
        earning.payment_fee = 0
        earning.net_amount = 0

        earning.save(
            update_fields=[
                "gross_amount",
                "platform_fee",
                "payment_fee",
                "net_amount",
                "updated_at",
            ]
        )

    AuditLog.objects.create(
        actor=None,
        action=AuditLog.AuditAction.REFUND_CREATED,
        entity_type="Order",
        entity_id=order.id,
        reason=f"Full refund confirmed by provider. Reason: {refund.reason}",
        metadata={
            "refund_id": refund.id,
            "order_id": order.id,
            "payment_id": order.payment.id,
            "amount_cents": order.payment.amount,
            "quantity": order.quantity,
        },
    )

    AuditLog.objects.create(
        actor=None,
        action=AuditLog.AuditAction.INVENTORY_UPDATED,
        entity_type="TicketType",
        entity_id=ticket_type.id,
        reason="Inventory increased after full refund.",
        metadata={
            "order_id": order.id,
            "refund_id": refund.id,
            "ticket_type": ticket_type.ticket_type,
            "quantity": order.quantity,
            "previous_inventory": previous_inventory,
            "new_inventory": ticket_type.available_inventory,
        },
    )

    return refund


@transaction.atomic
def mark_refund_failed(*, refund_id, detail):
    refund = Refund.objects.select_for_update().get(id=refund_id)

    if refund.status != Refund.RefundStatus.PENDING:
        return refund

    refund.status = Refund.RefundStatus.FAILED

    refund.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    AuditLog.objects.create(
        actor=None,
        action=AuditLog.AuditAction.REFUND_CREATED,
        entity_type="Order",
        entity_id=refund.order_id,
        reason=f"Refund failed before completion. Detail: {detail}",
        metadata={
            "refund_id": refund.id,
            "order_id": refund.order_id,
        },
    )

    return refund
