from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..selectors.eventselectors import get_published_events
from ..permissions import IsEventMaker
from ..serializers.eventserializer import EventCreateSerializer, EventReadSerializer

from ..services.create_event import create_event


class EventCreateAPIView(APIView):
    permission_classes = [IsEventMaker]

    def post(self, request):
        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = create_event(
            organizer=request.user,
            validated_data=serializer.validated_data,
        )
        return Response(
            EventReadSerializer(event).data,
            status=status.HTTP_201_CREATED,
        )


class EventListAPIView(APIView):
    def get(self, request):
        events = get_published_events()
        serializer = EventReadSerializer(events, many=True)
        return Response(serializer.data)
