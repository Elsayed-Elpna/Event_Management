from ..models.event import Event


def get_published_events():
    return (
        Event.objects.filter(status=Event.Status.PUBLISHED)
        .select_related("organizer")
        .order_by("starts_at")
    )


def get_event_by_id(*, event_id):
    return Event.objects.get(id=event_id)
