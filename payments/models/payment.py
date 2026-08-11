from django.db import models
from django.conf import settings

from common.models import BaseModel

# Create your models here.


class Payment(BaseModel):

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    class PaymentProvider(models.TextChoices):
        PAYMOB = "PAYMOB", "Paymob"

    class PaymentType(models.TextChoices):
        SUBSCRIPTION = "SUBSCRIPTION", "Subscription"
        ORDER = "ORDER", "Order"

    provider = models.CharField(
        max_length=20,
        choices=PaymentProvider.choices,
        default=PaymentProvider.PAYMOB,
    )

    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
    )

    provider_transaction_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
    )

    provider_reference = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    amount = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.payment_type} - {self.status}"
