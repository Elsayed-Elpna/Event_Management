from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from events.models.event import Event
from events.models.ticket_type import TicketType

from events.serializers.ticket_type_serializer import (
    TicketTypeSerializer,
    TicketTypeUpdateSerializer,
)
from events.services.ticket_type_service import create_ticket_type, update_ticket_type


class TicketTypeCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response(
                {"detail": "Event not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TicketTypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ticket_type = create_ticket_type(
                user=request.user,
                event=event,
                validated_data=serializer.validated_data,
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
            TicketTypeSerializer(ticket_type).data,
            status=status.HTTP_201_CREATED,
        )


class TicketTypeUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, ticket_type_id):
        try:
            ticket_type = TicketType.objects.select_related("event").get(
                id=ticket_type_id
            )
        except TicketType.DoesNotExist:
            return Response(
                {"detail": "Ticket type not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TicketTypeUpdateSerializer(
            ticket_type,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(raise_exception=True)

        try:
            ticket_type = update_ticket_type(
                user=request.user,
                ticket_type=ticket_type,
                validated_data=serializer.validated_data,
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
            TicketTypeSerializer(ticket_type).data,
            status=status.HTTP_200_OK,
        )
