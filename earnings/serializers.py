from rest_framework import serializers

from .models import Earning


class EarningSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source="order.id")
    event_title = serializers.CharField(
        source="order.reservation.ticket_type.event.title"
    )
    ticket_type = serializers.CharField(
        source="order.reservation.ticket_type.ticket_type"
    )
    quantity = serializers.IntegerField(source="order.quantity")

    class Meta:
        model = Earning
        fields = [
            "id",
            "order_id",
            "event_title",
            "ticket_type",
            "quantity",
            "gross_amount",
            "platform_fee",
            "payment_fee",
            "net_amount",
            "created_at",
        ]

        read_only_fields = fields
