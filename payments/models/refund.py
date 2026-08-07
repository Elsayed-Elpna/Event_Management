from django.db import models
from django.conf import settings

from common.models import BaseModel


class Refund(BaseModel):
    class RefundStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="refund",
    )

    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="refund",
    )

    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING,
    )

    refunded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Refund #{self.id}"
