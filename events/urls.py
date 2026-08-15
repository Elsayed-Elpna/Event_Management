from django.urls import path
from .views.eventview import (
    EventAPIView,
    EventDetailsAPIView,
    EventUpdateAPIView,
    PublishEventAPIView,
)

from .views.ticket_type_view import TicketTypeCreateAPIView, TicketTypeUpdateAPIView

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
    ############################
    # ticket types view
    ############################
    path(
        "<int:event_id>/ticket/",
        TicketTypeCreateAPIView.as_view(),
        name="ticket-types",
    ),
    path(
        "<int:ticket_type_id>/update-ticket/",
        TicketTypeUpdateAPIView.as_view(),
        name="ticket-type-update",
    ),
]
