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
            "capacity": ticket_type.capacity,
            "available_inventory": ticket_type.available_inventory,
        },
    )

    return ticket_type
