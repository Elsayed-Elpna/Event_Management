from django.db import transaction

from audit.models import AuditLog
from events.models.event import Event, EventStatus
from events.models.ticket_type import TicketType


@transaction.atomic
def create_ticket_type(*, user, event, validated_data):
    if not user.is_event_maker:
        raise PermissionError("Only event makers can create ticket types.")

    if event.organizer_id != user.id:
        raise PermissionError("You do not have permission to manage this event.")

    if event.status != EventStatus.DRAFT:
        raise ValueError("Ticket types can only be added to draft events.")

    if TicketType.objects.filter(
        event=event,
        ticket_type=validated_data["ticket_type"],
    ).exists():
        raise ValueError("This ticket type already exists for this event.")

    ticket_type = TicketType.objects.create(
        event=event,
        available_inventory=validated_data["capacity"],
        **validated_data,
    )

    AuditLog.objects.create(
        actor=user,
        action=AuditLog.AuditAction.TICKET_TYPE_CREATED,
        entity_type="TicketType",
        entity_id=ticket_type.id,
        reason="Ticket type created",
        metadata={
            "ticket_type": ticket_type.ticket_type,
            "capacity": ticket_type.capacity,
            "available_inventory": ticket_type.available_inventory,
        },
    )

    return ticket_type


@transaction.atomic
def update_ticket_type(*, user, ticket_type, validated_data):
    event = ticket_type.event

    if not user.is_event_maker:
        raise PermissionError("Only event makers can update ticket types.")

    if event.organizer_id != user.id:
        raise PermissionError("You do not have permission to manage this event.")

    if event.status != EventStatus.DRAFT:
        raise ValueError("Ticket types can only be updated while the event is draft.")

    if "price_cents" in validated_data:
        ticket_type.price_cents = validated_data["price_cents"]

    if "capacity" in validated_data:
        ticket_type.capacity = validated_data["capacity"]
        ticket_type.available_inventory = validated_data["capacity"]

    ticket_type.save(
        update_fields=[
            "price_cents",
            "updated_at",
            "capacity",
            "available_inventory",
        ]
    )

    return ticket_type
