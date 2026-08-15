from django.db import transaction, IntegrityError
from django.utils import timezone

from reservations.models import Reservation
from payments.models import Payment

from .models import Order
from audit.models import AuditLog
from payments.services.paymob_service import PaymobService
from events.models.ticket_type import TicketType


@transaction.atomic
def create_order(*, user, reservation_id, idempotency_key):

    # ---------------------------------
    # 1. Check existing order
    # ---------------------------------

    existing_order = Order.objects.filter(idempotency_key=idempotency_key).first()

    if existing_order:
        if existing_order.user_id != user.id:
            raise PermissionError("This idempotency key belongs to another user.")

        return existing_order

    # ---------------------------------
    # 2. Lock reservation
    # ---------------------------------

    reservation = (
        Reservation.objects.select_for_update()
        .select_related(
            "ticket_type",
            "ticket_type__event",
        )
        .get(id=reservation_id)
    )

    existing_reservation_order = Order.objects.filter(
        reservation_id=reservation.id
    ).first()

    if existing_reservation_order:
        if existing_reservation_order.user_id != user.id:
            raise PermissionError("You do not have permission to use this reservation.")

        return existing_reservation_order

    # ---------------------------------
    # 3. Validate ownership
    # ---------------------------------

    if reservation.user_id != user.id:
        raise PermissionError("You do not have permission to use this reservation.")

    # ---------------------------------
    # 4. Validate status
    # ---------------------------------

    if reservation.status != Reservation.ReservationStatus.HELD:
        raise ValueError("Only held reservations can be used to create an order.")

    # ---------------------------------
    # 5. Validate expiration
    # ---------------------------------

    if reservation.expires_at <= timezone.now():
        raise ValueError("Reservation has expired.")

    # ---------------------------------
    # 6. Calculate order amounts
    # ---------------------------------

    quantity = reservation.quantity
    unit_price = reservation.reserved_unit_price

    total_price = quantity * unit_price

    # ---------------------------------
    # 7. Create order
    # ---------------------------------

    try:
        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                reservation=reservation,
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price,
                platform_fee=0,
                payment_fee=0,
                organizer_amount=0,
                status=Order.OrderStatus.PENDING,
                idempotency_key=idempotency_key,
            )

            AuditLog.objects.create(
                actor=user,
                action=AuditLog.AuditAction.ORDER_CREATED,
                entity_type="Order",
                entity_id=order.id,
                reason="Order created by user",
                metadata={
                    "reservation_id": reservation.id,
                    "quantity": quantity,
                    "total_price": total_price,
                },
            )

    except IntegrityError:
        order = (
            Order.objects.filter(idempotency_key=idempotency_key).first()
            or Order.objects.filter(reservation=reservation).first()
        )
        if order is None:
            raise ValueError("This reservation already has an order.")

    return order


###########################
# Create payment
###########################


@transaction.atomic
def create_order_payment(*, user, order):
    order = (
        Order.objects.select_for_update(of=("self",))
        .select_related("payment")
        .get(id=order.id)
    )

    if order.user_id != user.id:
        raise PermissionError("You do not have permission to pay for this order.")

    if order.status != Order.OrderStatus.PENDING:
        raise ValueError("Only pending orders can be paid.")

    if order.payment:
        return order.payment

    payment = Payment.objects.create(
        payment_type=Payment.PaymentType.ORDER,
        amount=order.total_price,
        status=Payment.PaymentStatus.PENDING,
    )

    order.payment = payment

    order.save(
        update_fields=[
            "payment",
            "updated_at",
        ]
    )

    return payment


@transaction.atomic
def initiate_order_payment(*, user, order):
    order = (
        Order.objects.select_for_update(of=("self",))
        .select_related(
            "payment",
            "reservation",
            "reservation__ticket_type",
            "reservation__ticket_type__event",
        )
        .get(id=order.id)
    )

    if order.user_id != user.id:
        raise PermissionError("You do not have permission to pay for this order.")

    if order.status != Order.OrderStatus.PENDING:
        raise ValueError("Only pending orders can be paid.")

    if not order.payment:
        payment = create_order_payment(
            user=user,
            order=order,
        )
        order.payment = payment
    else:
        payment = order.payment

    if payment.status != Payment.PaymentStatus.PENDING:
        raise ValueError("Only pending payments can be initiated.")

    if payment.provider_reference and payment.client_secret:
        return {
            "order": order,
            "payment": payment,
            "client_secret": payment.client_secret,
        }

    paymob = PaymobService()

    intention = paymob.create_order_intention(
        order=order,
    )

    payment.provider_reference = intention["id"]
    payment.client_secret = intention["client_secret"]

    payment.save(
        update_fields=[
            "provider_reference",
            "client_secret",
            "updated_at",
        ]
    )

    return {
        "order": order,
        "payment": payment,
        "client_secret": intention["client_secret"],
    }
