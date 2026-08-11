from django.db import transaction


from events.models.event import EventStatus, Event
from audit.models import AuditLog
from subscriptions.models import SubscriptionStatus


@transaction.atomic
def create_event(*, user, validated_data):
    subscription = getattr(user, "subscription", None)

    if not subscription or subscription.status != SubscriptionStatus.ACTIVE:
        raise PermissionError(
            "Active subscription is required to create an event.",
        )

    event = Event.objects.create(
        organizer=user,
        status=EventStatus.DRAFT,
        **validated_data,
    )

    AuditLog.objects.create(
        actor=user,
        action=AuditLog.AuditAction.EVENT_CREATED,
        entity_type="Event",
        entity_id=event.id,
        reason="Event created by organizer",
    )

    return event


@transaction.atomic
def publish_event(*, user, event):

    if not user.is_event_maker:
        raise PermissionError("Only event makers can publish events.")

    if event.organizer_id != user.id:
        raise PermissionError("You do not have permission to publish this event.")

    if event.status != EventStatus.DRAFT:
        raise ValueError("Only draft events can be published.")

    if not event.ticket_types.exists():
        raise ValueError("Event must have at least one ticket type before publishing.")

    if not event.ticket_types.filter(capacity__gt=0).exists():
        raise ValueError("Event must have a ticket type with available capacity.")

    event.status = EventStatus.PUBLISHED

    event.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    AuditLog.objects.create(
        actor=user,
        action=AuditLog.AuditAction.EVENT_PUBLISHED,
        entity_type="Event",
        entity_id=event.id,
        reason="Event published",
    )

    return event
