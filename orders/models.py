from django.db import models
from django.conf import settings

from common.models import BaseModel


# Create your models here.
class Order(BaseModel):
    class OrderStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )

    reservation = models.OneToOneField(
        "reservations.Reservation",
        on_delete=models.PROTECT,
        related_name="order",
    )

    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="order",
        null=True,
        blank=True,
    )

    quantity = models.PositiveIntegerField()

    unit_price = models.PositiveIntegerField()

    total_price = models.PositiveIntegerField()

    platform_fee = models.PositiveIntegerField(default=0)

    payment_fee = models.PositiveIntegerField(default=0)

    organizer_amount = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )

    idempotency_key = models.UUIDField(unique=True)

    def __str__(self):
        return f"Order #{self.id} - reservation#{self.reservation_id} - user#{self.user_id}"
