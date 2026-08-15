from django.urls import path

from .views import (
    OrderCreateAPIView,
    OrderPaymentAPIView,
    MyOrdersAPIView,
    OrderRefundAPIView,
)

urlpatterns = [
    path(
        "create/",
        OrderCreateAPIView.as_view(),
        name="order-create",
    ),
    path(
        "<int:order_id>/payment/",
        OrderPaymentAPIView.as_view(),
        name="order-payment",
    ),
    path(
        "<int:order_id>/refund/",
        OrderRefundAPIView.as_view(),
        name="order-refund",
    ),
    path("", MyOrdersAPIView.as_view(), name="my-orders"),
]
