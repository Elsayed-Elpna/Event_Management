from rest_framework import serializers

from events.models import Event


class EventCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "location",
            "starts_at",
            "ends_at",
            "hold_duration",
        ]

    def validate(self, attrs):
        if attrs["starts_at"] >= attrs["ends_at"]:
            raise serializers.ValidationError(
                "Start date must be before end date",
            )

        return attrs


class EventReadSerializer(serializers.ModelSerializer):
    organizer = serializers.EmailField(
        source="organizer.email",
        read_only=True,
    )

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
            "organizer",
            "created_at",
        ]
