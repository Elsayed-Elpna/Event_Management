from rest_framework import serializers

from .models import Balance


class BalanceRecordSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source="order.id")
    event_title = serializers.CharField(
        source="order.reservation.ticket_type.event.title"
    )
    event_starts_at = serializers.DateTimeField(
        source="order.reservation.ticket_type.event.starts_at",
        allow_null=True,
        default=None,
    )
    ticket_type = serializers.CharField(
        source="order.reservation.ticket_type.ticket_type"
    )
    quantity = serializers.IntegerField(source="order.quantity")
    unit_price = serializers.IntegerField(source="order.unit_price")

    transaction_id = serializers.CharField(
        source="order.payment.provider_transaction_id",
        allow_null=True,
        default=None,
    )
    intention_reference = serializers.CharField(
        source="order.payment.provider_reference",
        allow_null=True,
        default=None,
    )
    payment_status = serializers.CharField(
        source="order.payment.status",
        allow_null=True,
        default=None,
    )
    paid_at = serializers.DateTimeField(
        source="order.payment.paid_at",
        allow_null=True,
        default=None,
    )

    refunded_at = serializers.DateTimeField(
        source="order.refund.refunded_at",
        allow_null=True,
        default=None,
    )

    class Meta:
        model = Balance
        fields = [
            "id",
            "order_id",
            "event_title",
            "event_starts_at",
            "ticket_type",
            "quantity",
            "unit_price",
            "gross_amount",
            "platform_fee",
            "payment_fee",
            "net_amount",
            "transaction_id",
            "intention_reference",
            "payment_status",
            "paid_at",
            "refunded_at",
            "created_at",
        ]

        read_only_fields = fields
