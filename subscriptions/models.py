from django.db import models
from django.conf import settings
from common.models import BaseModel

# Create your models here.


class SubscriptionStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACTIVE = "ACTIVE", "Active"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"


class Subscription(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )

    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="subscription",
        null=True,
        blank=True,
    )

    amount_cents = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.PENDING,
    )

    starts_at = models.DateTimeField(null=True, blank=True)

    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"user#{self.user_id} - {self.status}"
