from django.urls import path

from .views import PaymobWebhookAPIView

urlpatterns = [
    path(
        "webhook/",
        PaymobWebhookAPIView.as_view(),
        name="paymob-webhook",
    ),
]
