from rest_framework import serializers

from events.models import Event
from events.serializers.ticket_type_serializer import TicketTypeSerializer


class EventSerializer(serializers.ModelSerializer):
    ticket_types = TicketTypeSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "location",
            "status",
            "starts_at",
            "ends_at",
            "hold_duration",
            "ticket_types",
        ]
        read_only_fields = ["id", "status", "ticket_types"]

    def validate(self, attrs):
        if (
            attrs.get("starts_at")
            and attrs.get("ends_at")
            and attrs["starts_at"] >= attrs["ends_at"]
        ):
            raise serializers.ValidationError(
                "Event end time must be after start time."
            )

        if attrs.get("hold_duration") is not None and attrs["hold_duration"] <= 0:
            raise serializers.ValidationError(
                "Hold duration must be greater than zero."
            )

        return attrs
