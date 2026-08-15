from django.urls import path

from .views import (
    ReservationCreateAPIView,
    MyReservationsAPIView,
    ReservationCancelAPIView,
)

urlpatterns = [
    path(
        "",
        ReservationCreateAPIView.as_view(),
        name="reservation-create",
    ),
    path(
        "me/",
        MyReservationsAPIView.as_view(),
        name="my-reservations",
    ),
    path(
        "<int:reservation_id>/cancel/",
        ReservationCancelAPIView.as_view(),
        name="reservation-cancel",
    ),
]
