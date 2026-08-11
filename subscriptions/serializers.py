from rest_framework import serializers

from .models import Subscription


class SubscriptionCreateSerializer(serializers.Serializer):
    def validate(self, attrs):
        request = self.context["request"]

        if hasattr(request.user, "subscription"):
            raise serializers.ValidationError("User already has a subscription")

        return attrs


class SubscriptionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Subscription
        fields = ["user_email", "amount_cents", "status", "starts_at", "expires_at"]
