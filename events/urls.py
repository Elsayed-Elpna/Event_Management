from django.urls import path
from .views.eventview import (
    EventAPIView,
    EventDetailsAPIView,
    EventUpdateAPIView,
    PublishEventAPIView,
)

urlpatterns = [
    path(
        "",
        EventAPIView.as_view(),
        name="events",
    ),
    path(
        "<int:event_id>/",
        EventDetailsAPIView.as_view(),
        name="event-details",
    ),
    path(
        "<int:event_id>/update/",
        EventUpdateAPIView.as_view(),
        name="event-update",
    ),
    path(
        "<int:event_id>/publish/",
        PublishEventAPIView.as_view(),
        name="event-publish",
    ),
]
