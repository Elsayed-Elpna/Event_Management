from rest_framework import serializers

from .models import Subscription, SubscriptionStatus


class SubscriptionCreateSerializer(serializers.Serializer):
    def validate(self, attrs):
        request = self.context["request"]

        subscription = getattr(request.user, "subscription", None)

        if subscription is not None and subscription.status == SubscriptionStatus.ACTIVE:
            raise serializers.ValidationError("User already has an active subscription")

        return attrs


class SubscriptionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Subscription
        fields = ["user_email", "amount_cents", "status", "starts_at", "expires_at"]
