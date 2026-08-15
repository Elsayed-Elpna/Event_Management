from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Reservation

from .serializer import ReservationCreateSerializer, ReservationSerializer
from .services import create_reservation, cancel_reservation

# Create your views here.


class ReservationCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            reservation = create_reservation(
                user=request.user,
                validated_data=serializer.validated_data,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_201_CREATED,
        )


class MyReservationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reservations = (
            Reservation.objects.filter(user=request.user)
            .select_related("ticket_type", "ticket_type__event")
            .order_by("-created_at")
        )

        serializer = ReservationSerializer(
            reservations,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class ReservationCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reservation_id):
        try:
            reservation = Reservation.objects.get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response(
                {"detail": "Reservation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            reservation = cancel_reservation(
                user=request.user,
                reservation=reservation,
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
            ReservationSerializer(reservation).data,
            status=status.HTTP_200_OK,
        )
