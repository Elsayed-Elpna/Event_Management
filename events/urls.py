from django.urls import path
from .views.eventview import EventCreateAPIView, EventListAPIView

urlpatterns = [
    path(
        "",
        EventListAPIView.as_view(),
        name="event-list",
    ),
    path(
        "create/",
        EventCreateAPIView.as_view(),
        name="event-create",
    ),
]
