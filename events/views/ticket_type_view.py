from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from events.models import Event

from events.serializers.ticket_type_serializer import TicketTypeSerializer
from events.services.ticket_type_service import create_ticket_type


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
