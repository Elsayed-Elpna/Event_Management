from django.conf import settings
from django.shortcuts import render

# Create your views here.

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subscription
from .serializers import SubscriptionCreateSerializer, SubscriptionSerializer
from .service.create_sub_service import create_subscription


class SubscriptionCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubscriptionCreateSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        subscription, paymob_response = create_subscription(
            user=request.user,
        )

        checkout_url = (
            f"{settings.PAYMOB_BASE_URL}/unifiedcheckout/"
            f"?publicKey={settings.PAYMOB_PUBLIC_KEY}"
            f"&clientSecret={paymob_response['client_secret']}"
        )

        return Response(
            {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "amount_cents": subscription.amount_cents,
                "checkout_url": checkout_url,
                "payment": {
                    "id": subscription.payment.id,
                    "status": subscription.payment.status,
                    "provider": subscription.payment.provider,
                    "provider_reference": (subscription.payment.provider_reference),
                    "client_secret": paymob_response["client_secret"],
                },
            },
            status=status.HTTP_201_CREATED,
        )


class MySubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            subscription = Subscription.objects.select_related("user").get(
                user=request.user
            )
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "You do not have a subscription."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscriptionSerializer(subscription)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
