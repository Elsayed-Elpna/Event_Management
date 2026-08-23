from django.db import models
from django.conf import settings
from common.models import BaseModel

# Create your models here.


class Earning(BaseModel):
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="earnings",
    )

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="earning",
    )

    gross_amount = models.PositiveIntegerField()

    platform_fee = models.PositiveIntegerField()

    payment_fee = models.PositiveIntegerField()

    net_amount = models.PositiveIntegerField()

    def __str__(self):
        return f"Order #{self.order_id}"
