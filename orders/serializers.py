from rest_framework import serializers

from .models import Order


class OrderCreateSerializer(serializers.Serializer):
    reservation_id = serializers.IntegerField()
    idempotency_key = serializers.UUIDField()


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "id",
            "reservation",
            "quantity",
            "unit_price",
            "total_price",
            "platform_fee",
            "payment_fee",
            "organizer_amount",
            "status",
            "idempotency_key",
        ]

        read_only_fields = [
            "id",
            "reservation",
            "quantity",
            "unit_price",
            "total_price",
            "platform_fee",
            "payment_fee",
            "organizer_amount",
            "status",
        ]


class OrderPaymentResponseSerializer(serializers.Serializer):
    checkout_url = serializers.CharField()

    order_id = serializers.IntegerField()
    payment_id = serializers.IntegerField()
    status = serializers.CharField()
    amount_cents = serializers.IntegerField()
    client_secret = serializers.CharField()


class OrderRefundRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        default="",
    )
