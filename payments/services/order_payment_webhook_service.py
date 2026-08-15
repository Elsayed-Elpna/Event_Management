from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from audit.models import AuditLog
from orders.models import Order
from payments.models import Payment
from reservations.models import Reservation
from earnings.models import Earning


@transaction.atomic
def process_successful_order_payment(*, transaction_data):

    merchant_order_id = transaction_data["order"]["merchant_order_id"]

    if not merchant_order_id.startswith("order-"):
        raise ValueError("Unsupported merchant order")

    parts = merchant_order_id.split("-")

    if len(parts) != 4:
        raise ValueError("Invalid order merchant order")

    order_id = parts[1]
    payment_id = parts[3]

    # ---------------------------------
    # 1. Lock order
    # ---------------------------------

    order = (
        Order.objects.select_for_update(of=("self",))
        .select_related(
            "payment",
            "reservation",
        )
        .get(id=order_id)
    )

    payment = order.payment

    if payment is None:
        raise ValueError("Order does not have a payment.")

    # ---------------------------------
    # 2. Validate payment ownership
    # ---------------------------------

    if payment.id != int(payment_id):
        raise ValueError("Payment does not belong to order.")

    # ---------------------------------
    # 3. Validate amount
    # ---------------------------------

    if payment.amount != transaction_data["amount_cents"]:
        raise ValueError("Payment amount mismatch.")

    # ---------------------------------
    # 4. Idempotency
    # ---------------------------------

    if payment.status == Payment.PaymentStatus.SUCCESS:
        return order

    # ---------------------------------
    # 5. Update payment
    # ---------------------------------

    transaction_id = str(transaction_data["id"])

    payment.provider_transaction_id = transaction_id
    payment.status = Payment.PaymentStatus.SUCCESS
    payment.paid_at = parse_datetime(transaction_data["created_at"])

    payment.save(
        update_fields=[
            "provider_transaction_id",
            "status",
            "paid_at",
            "updated_at",
        ]
    )

    # ---------------------------------
    # 6. Update order
    # ---------------------------------

    order.status = Order.OrderStatus.PAID

    order.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    # ---------------------------------
    # 7. Lock reservation
    # ---------------------------------

    reservation = Reservation.objects.select_for_update().get(id=order.reservation_id)

    # ---------------------------------
    # 8. Validate reservation
    # ---------------------------------

    if reservation.status != Reservation.ReservationStatus.HELD:
        raise ValueError("Only held reservations can be confirmed.")

    if reservation.expires_at <= timezone.now():
        raise ValueError("Reservation has expired.")

    # ---------------------------------
    # 9. Confirm reservation
    # ---------------------------------

    reservation.status = Reservation.ReservationStatus.CONFIRMED

    reservation.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    # ---------------------------------
    # 10. Audit log
    # ---------------------------------

    AuditLog.objects.create(
        actor=order.user,
        action=AuditLog.AuditAction.ORDER_PAID,
        entity_type="Order",
        entity_id=order.id,
        reason="Order paid and reservation confirmed.",
        metadata={
            "order_id": order.id,
            "payment_id": payment.id,
            "reservation_id": reservation.id,
            "quantity": reservation.quantity,
        },
    )

    earning = Earning.objects.filter(order=order).first()

    if earning is None:
        gross_amount = order.total_price

        platform_fee = order.platform_fee
        payment_fee = order.payment_fee

        net_amount = gross_amount - platform_fee - payment_fee

        Earning.objects.create(
            organizer=reservation.ticket_type.event.organizer,
            order=order,
            gross_amount=gross_amount,
            platform_fee=platform_fee,
            payment_fee=payment_fee,
            net_amount=net_amount,
        )

    return order
