from django.urls import path

from .views import MyEarningsAPIView

urlpatterns = [
    path("", MyEarningsAPIView.as_view(), name="my-earnings"),
]
