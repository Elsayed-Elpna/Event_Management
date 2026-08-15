from django.db import transaction
from django.utils import timezone

from audit.models import AuditLog
from events.models.ticket_type import TicketType
from orders.models import Order
from payments.models import Payment, Refund
from payments.services.paymob_service import PaymobService


@transaction.atomic
def process_order_refund(*, user, order_id, reason):
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

    refund = Refund.objects.create(
        order=order,
        reason=reason,
        status=Refund.RefundStatus.SUCCESS,
        refunded_at=timezone.now(),
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
        actor=user,
        action=AuditLog.AuditAction.REFUND_CREATED,
        entity_type="Order",
        entity_id=order.id,
        reason=f"Full refund issued. Reason: {reason}",
        metadata={
            "refund_id": refund.id,
            "order_id": order.id,
            "payment_id": order.payment.id,
            "amount_cents": order.payment.amount,
            "quantity": order.quantity,
        },
    )

    AuditLog.objects.create(
        actor=user,
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

    PaymobService().create_refund(
        transaction_id=order.payment.provider_transaction_id,
        amount_cents=order.payment.amount,
        description=reason,
    )

    return refund
