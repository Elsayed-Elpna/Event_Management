from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from events.models.event import Event, EventStatus


from events.serializers.eventserializer import EventSerializer
from events.permissions import IsEventMaker
from events.services.eventservices import create_event, publish_event


class EventAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsEventMaker()]
        return [IsAuthenticated()]

    def get(self, request):
        if request.user.is_event_maker:
            events = Event.objects.filter(organizer=request.user).prefetch_related(
                "ticket_types"
            )
        else:
            events = Event.objects.filter(status=EventStatus.PUBLISHED).prefetch_related(
                "ticket_types"
            )

        serializer = EventSerializer(
            events,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = EventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            event = create_event(
                user=request.user,
                validated_data=serializer.validated_data,
            )
        except PermissionError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            EventSerializer(event).data,
            status=status.HTTP_201_CREATED,
        )


class EventDetailsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response(
                {"detail": "Event not found."}, status=status.HTTP_404_NOT_FOUND
            )

        is_published = event.status == EventStatus.PUBLISHED
        is_owner = request.user.is_event_maker and event.organizer_id == request.user.id

        if not (is_published or is_owner):
            return Response(
                {"detail": "Event not found."}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(EventSerializer(event).data, status=status.HTTP_200_OK)


class EventUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsEventMaker]

    def patch(self, request, event_id):
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response(
                {"detail": "Event not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not request.user.is_event_maker or event.organizer_id != request.user.id:
            return Response(
                {"detail": "You do not have permission to update this event."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = EventSerializer(
            event,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class PublishEventAPIView(APIView):
    permission_classes = [IsAuthenticated, IsEventMaker]

    def post(self, request, event_id):
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response(
                {"detail": "Event not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            event = publish_event(
                user=request.user,
                event=event,
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
            EventSerializer(event).data,
            status=status.HTTP_200_OK,
        )
