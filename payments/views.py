from django.shortcuts import render

import logging

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .services.paymob_service import PaymobService
from .services.payments_webhook_service import process_successful_payment
from .services.order_payment_webhook_service import (
    WebhookIgnoredError,
    process_successful_order_payment,
)

logger = logging.getLogger(__name__)


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

        merchant_order_id = transaction_data["order"]["merchant_order_id"]

        # ---------------------------------
        # Subscription Payment
        # ---------------------------------

        if merchant_order_id.startswith("subscription-"):
            try:
                subscription = process_successful_payment(
                    transaction_data=transaction_data,
                )
            except WebhookIgnoredError as exc:
                logger.warning(
                    "Ignoring subscription webhook: %s", exc
                )
                return Response(
                    {
                        "status": "ignored",
                        "reason": str(exc),
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception:
                logger.exception(
                    "Failed to process subscription webhook; acknowledging to stop retries."
                )
                return Response(
                    {
                        "status": "ignored",
                        "reason": "internal_error",
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {
                    "status": "payment_processed",
                    "payment_type": "subscription",
                    "subscription_id": subscription.id,
                },
                status=status.HTTP_200_OK,
            )

        # ---------------------------------
        # Order Payment
        # ---------------------------------

        elif merchant_order_id.startswith("order-"):
            try:
                order = process_successful_order_payment(
                    transaction_data=transaction_data,
                )
            except WebhookIgnoredError as exc:
                logger.warning("Ignoring order webhook: %s", exc)
                return Response(
                    {
                        "status": "ignored",
                        "reason": str(exc),
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception:
                logger.exception(
                    "Failed to process order webhook; acknowledging to stop retries."
                )
                return Response(
                    {
                        "status": "ignored",
                        "reason": "internal_error",
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {
                    "status": "payment_processed",
                    "payment_type": "order",
                    "order_id": order.id,
                },
                status=status.HTTP_200_OK,
            )

        # ---------------------------------
        # Unsupported Payment
        # ---------------------------------

        return Response(
            {"detail": "Unsupported merchant order."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get(self, request):
        return Response(
            {"status": "received"},
            status=status.HTTP_200_OK,
        )
