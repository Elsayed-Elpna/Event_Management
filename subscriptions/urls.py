from django.urls import path
from .views import SubscriptionCreateAPIView, MySubscriptionAPIView

urlpatterns = [
    path(
        "",
        SubscriptionCreateAPIView.as_view(),
        name="subscription-create",
    ),
    path(
        "me/",
        MySubscriptionAPIView.as_view(),
        name="my-subscription",
    ),
]
