from datetime import timedelta


from django.utils import timezone
from django.db import transaction


from audit.models import AuditLog
from events.models.event import Event, EventStatus
from events.models.ticket_type import TicketType
from .models import Reservation


@transaction.atomic
def create_reservation(*, user, validated_data):
    ticket_type = validated_data["ticket_type"]
    quantity = validated_data["quantity"]

    ticket_type = (
        TicketType.objects.select_for_update()
        .select_related("event")
        .get(id=ticket_type.id)
    )

    if ticket_type.event.status != EventStatus.PUBLISHED:
        raise ValueError("Reservations can only be created for published events.")

    if ticket_type.event.ends_at <= timezone.now():
        raise ValueError("Cannot reserve tickets for an event that has already ended.")

    if quantity > ticket_type.available_inventory:
        raise ValueError("Not enough tickets available.")

    expires_at = timezone.now() + timedelta(minutes=ticket_type.event.hold_duration)

    reservation = Reservation.objects.create(
        user=user,
        ticket_type=ticket_type,
        quantity=quantity,
        expires_at=expires_at,
        status=Reservation.ReservationStatus.HELD,
        reserved_unit_price=ticket_type.price_cents,
    )

    ticket_type.available_inventory -= quantity

    ticket_type.save(
        update_fields=[
            "available_inventory",
            "updated_at",
        ]
    )

    AuditLog.objects.create(
        actor=user,
        action=AuditLog.AuditAction.RESERVATION_CREATED,
        entity_type="Reservation",
        entity_id=reservation.id,
        reason="Reservation created",
        metadata={
            "ticket_type": ticket_type.ticket_type,
            "quantity": quantity,
            "reserved_unit_price": reservation.reserved_unit_price,
            "expires_at": reservation.expires_at.isoformat(),
        },
    )

    return reservation


@transaction.atomic
def cancel_reservation(*, user, reservation):
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("ticket_type")
        .get(id=reservation.id)
    )

    if reservation.user_id != user.id:
        raise PermissionError("You do not have permission to cancel this reservation.")

    if reservation.status != Reservation.ReservationStatus.HELD:
        raise ValueError("Only held reservations can be cancelled.")

    ticket_type = TicketType.objects.select_for_update().get(
        id=reservation.ticket_type_id
    )

    ticket_type.available_inventory += reservation.quantity

    ticket_type.save(
        update_fields=[
            "available_inventory",
            "updated_at",
        ]
    )

    reservation.status = Reservation.ReservationStatus.CANCELLED

    reservation.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    AuditLog.objects.create(
        actor=user,
        action=AuditLog.AuditAction.RESERVATION_CANCELLED,
        entity_type="Reservation",
        entity_id=reservation.id,
        reason="Reservation cancelled",
        metadata={
            "ticket_type": ticket_type.ticket_type,
            "quantity": reservation.quantity,
            "restored_inventory": reservation.quantity,
        },
    )

    return reservation


@transaction.atomic
def confirm_reservation(*, reservation):
    reservation = Reservation.objects.select_for_update().get(id=reservation.id)

    if reservation.status != Reservation.ReservationStatus.HELD:
        raise ValueError("Only held reservations can be confirmed.")

    reservation.status = Reservation.ReservationStatus.CONFIRMED

    reservation.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return reservation
