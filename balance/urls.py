from django.urls import path
from .views import MyBalanceAPIView

urlpatterns = [
    path("", MyBalanceAPIView.as_view(), name="my-balance"),
]
