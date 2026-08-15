from django.db import transaction
from django.utils import timezone

from audit.models import AuditLog
from events.models.event import Event, EventStatus
from events.models.ticket_type import TicketType
from orders.models import Order
from payments.models import Payment
from reservations.models import Reservation
from subscriptions.models import Subscription, SubscriptionStatus


@transaction.atomic
def expire_subscriptions():
    now = timezone.now()

    subscriptions = list(
        Subscription.objects.select_for_update().filter(
            status=SubscriptionStatus.ACTIVE,
            expires_at__lte=now,
        )
    )

    for subscription in subscriptions:
        subscription.status = SubscriptionStatus.EXPIRED

        subscription.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        AuditLog.objects.create(
            actor=None,
            action=AuditLog.AuditAction.SUBSCRIPTION_EXPIRED,
            entity_type="Subscription",
            entity_id=subscription.id,
            reason="Subscription expired.",
            metadata={
                "user_id": subscription.user_id,
                "expires_at": subscription.expires_at.isoformat(),
            },
        )

    return len(subscriptions)


@transaction.atomic
def finish_events():
    now = timezone.now()

    events = list(
        Event.objects.select_for_update()
        .exclude(status=EventStatus.CANCELLED)
        .filter(
            ends_at__lte=now,
        )
    )

    for event in events:
        event.status = EventStatus.FINISHED

        event.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        AuditLog.objects.create(
            actor=None,
            action=AuditLog.AuditAction.EVENT_FINISHED,
            entity_type="Event",
            entity_id=event.id,
            reason="Event ended.",
            metadata={
                "ends_at": event.ends_at.isoformat(),
                "organizer_id": event.organizer_id,
            },
        )

    return len(events)


@transaction.atomic
def expire_reservations():
    now = timezone.now()

    reservations = list(
        Reservation.objects.select_for_update()
        .filter(
            status=Reservation.ReservationStatus.HELD,
            expires_at__lte=now,
        )
        .select_related("ticket_type")
    )

    ticket_type_ids = {r.ticket_type_id for r in reservations}

    locked_ticket_types = {
        tt.id: tt
        for tt in TicketType.objects.select_for_update().filter(id__in=ticket_type_ids)
    }

    for reservation in reservations:
        ticket_type = locked_ticket_types[reservation.ticket_type_id]

        ticket_type.available_inventory += reservation.quantity

        ticket_type.save(
            update_fields=[
                "available_inventory",
                "updated_at",
            ]
        )

        reservation.status = Reservation.ReservationStatus.EXPIRED

        reservation.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        AuditLog.objects.create(
            actor=None,
            action=AuditLog.AuditAction.RESERVATION_EXPIRED,
            entity_type="Reservation",
            entity_id=reservation.id,
            reason="Reservation hold expired.",
            metadata={
                "user_id": reservation.user_id,
                "ticket_type": ticket_type.ticket_type,
                "quantity": reservation.quantity,
                "restored_inventory": reservation.quantity,
                "expires_at": reservation.expires_at.isoformat(),
            },
        )

    return len(reservations)


@transaction.atomic
def fail_expired_orders():
    orders = list(
        Order.objects.select_for_update(of=("self",)).filter(
            status=Order.OrderStatus.PENDING,
            reservation__status=Reservation.ReservationStatus.EXPIRED,
        )
    )

    pending_payment_ids = [o.payment_id for o in orders if o.payment_id is not None]

    locked_payments = {
        payment.id: payment
        for payment in Payment.objects.select_for_update().filter(
            id__in=pending_payment_ids,
            status=Payment.PaymentStatus.PENDING,
        )
    }

    for order in orders:
        order.status = Order.OrderStatus.FAILED

        order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        payment = locked_payments.get(order.payment_id)

        if payment is not None:
            payment.status = Payment.PaymentStatus.FAILED

            payment.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        AuditLog.objects.create(
            actor=None,
            action=AuditLog.AuditAction.ORDER_FAILED,
            entity_type="Order",
            entity_id=order.id,
            reason="Order failed because its reservation expired.",
            metadata={
                "user_id": order.user_id,
                "reservation_id": order.reservation_id,
            },
        )

    return len(orders)
