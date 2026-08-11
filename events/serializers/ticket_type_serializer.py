from events.models import TicketType
from rest_framework import serializers


class TicketTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        fields = ["id", "name", "price_cents", "capacity", "available_inventory"]
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
