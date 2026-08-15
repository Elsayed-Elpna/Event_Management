from rest_framework import serializers

from .models import Reservation


class ReservationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            "ticket_type",
            "quantity",
        ]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")

        return value


class ReservationSerializer(serializers.ModelSerializer):
    event = serializers.CharField(source="ticket_type.event", read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id",
            "event",
            "ticket_type",
            "quantity",
            "expires_at",
            "status",
            "reserved_unit_price",
        ]
        read_only_fields = [
            "id",
            "expires_at",
            "status",
            "reserved_unit_price",
        ]
