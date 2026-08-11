from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .services.paymob_service import PaymobService
from .services.payments_webhook_service import process_successful_payment


class PaymobWebhookAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        transaction_data = request.data.get("obj")

        if not transaction_data:
            return Response(
                {"detail": "Invalid webhook payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        received_hmac = request.query_params.get("hmac")

        if not received_hmac:
            return Response(
                {"detail": "Missing HMAC"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paymob_service = PaymobService()

        is_valid = paymob_service.verify_transaction_hmac(
            transaction_data=transaction_data,
            received_hmac=received_hmac,
        )

        if not is_valid:
            return Response(
                {"detail": "Invalid HMAC"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not transaction_data["success"]:
            return Response(
                {"status": "payment_failed"},
                status=status.HTTP_200_OK,
            )

        subscription = process_successful_payment(
            transaction_data=transaction_data,
        )

        return Response(
            {
                "status": "payment_processed",
                "subscription_id": subscription.id,
            },
            status=status.HTTP_200_OK,
        )

    def get(self, request):
        return Response(
            {"status": "received"},
            status=status.HTTP_200_OK,
        )
