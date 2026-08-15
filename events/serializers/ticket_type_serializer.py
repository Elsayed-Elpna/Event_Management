from events.models import TicketType
from rest_framework import serializers


class TicketTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        fields = [
            "id",
            "ticket_type",
            "price_cents",
            "capacity",
            "available_inventory",
        ]
        read_only_fields = ["id", "available_inventory"]

    def validate(self, attrs):
        if attrs["capacity"] <= 0:
            raise serializers.ValidationError(
                {"capacity": "Capacity must be greater than zero."}
            )

        if attrs["price_cents"] <= 0:
            raise serializers.ValidationError(
                {"price_cents": "Price must be greater than zero."}
            )

        return attrs


class TicketTypeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        fields = [
            "price_cents",
            "capacity",
        ]

    def validate_price_cents(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")

        return value

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Capacity must be greater than zero.")

        return value
