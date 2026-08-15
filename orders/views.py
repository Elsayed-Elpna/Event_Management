from django.conf import settings
from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reservations.models import Reservation
from .models import Order

from .serializers import (
    OrderSerializer,
    OrderCreateSerializer,
    OrderPaymentResponseSerializer,
    OrderRefundRequestSerializer,
)


from .service import create_order, initiate_order_payment
from payments.services.refund_service import process_order_refund

# Create your views here.


class OrderCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        try:
            order = create_order(
                user=request.user,
                reservation_id=serializer.validated_data["reservation_id"],
                idempotency_key=serializer.validated_data["idempotency_key"],
            )

        except PermissionError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Reservation.DoesNotExist:
            return Response(
                {"detail": "Reservation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class OrderPaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)

            result = initiate_order_payment(
                user=request.user,
                order=order,
            )

        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        except PermissionError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = {
            "order_id": result["order"].id,
            "payment_id": result["payment"].id,
            "status": result["payment"].status,
            "amount_cents": result["payment"].amount,
            "client_secret": result["client_secret"],
            "checkout_url": (
                f"{settings.PAYMOB_BASE_URL}/unifiedcheckout/"
                f"?publicKey={settings.PAYMOB_PUBLIC_KEY}"
                f"&clientSecret={result['client_secret']}"
            ),
        }

        serializer = OrderPaymentResponseSerializer(response_data)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class MyOrdersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects.filter(user=request.user)
            .select_related(
                "reservation",
                "reservation__ticket_type",
                "reservation__ticket_type__event",
            )
            .order_by("-created_at")
        )
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderRefundAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        serializer = OrderRefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refund = process_order_refund(
                user=request.user,
                order_id=order_id,
                reason=serializer.validated_data["reason"],
            )

        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        except PermissionError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "refund_id": refund.id,
                "order_id": refund.order_id,
                "status": refund.status,
                "reason": refund.reason,
                "refunded_at": refund.refunded_at,
            },
            status=status.HTTP_201_CREATED,
        )
