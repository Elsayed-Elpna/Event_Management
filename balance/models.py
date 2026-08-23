from django.db import models
from django.conf import settings

from common.models import BaseModel


class Balance(BaseModel):
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="balances",
    )

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="balance",
    )

    gross_amount = models.PositiveIntegerField()

    platform_fee = models.PositiveIntegerField()

    payment_fee = models.PositiveIntegerField()

    net_amount = models.PositiveIntegerField()

    def __str__(self):
        return f"Balance for order #{self.order_id}"
