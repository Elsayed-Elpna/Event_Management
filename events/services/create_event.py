from ..models import Event


def create_event(*, organizer, validated_data):
    event = Event.objects.create(
        organizer=organizer,
        **validated_data,
    )
    return event
