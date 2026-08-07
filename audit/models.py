from django.db import models
from django.conf import settings

from common.models import BaseModel

# Create your models here.


class AuditLog(BaseModel):
    class AuditAction(models.TextChoices):
        EVENT_CREATED = "EVENT_CREATED", "Event Created"
        RESERVATION_CREATED = "RESERVATION_CREATED", "Reservation Created"
        RESERVATION_EXPIRED = "RESERVATION_EXPIRED", "Reservation Expired"
        ORDER_PAID = "ORDER_PAID", "Order Paid"
        REFUND_CREATED = "REFUND_CREATED", "Refund Created"
        INVENTORY_UPDATED = "INVENTORY_UPDATED", "Inventory Updated"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    metadata = models.JSONField(default=dict, blank=True)

    action = models.CharField(
        max_length=255,
        choices=AuditAction.choices,
    )

    entity_type = models.CharField(max_length=255)

    entity_id = models.PositiveBigIntegerField()

    reason = models.TextField(blank=True)

    def __str__(self):
        return f"{self.actor} - {self.action} - {self.entity_type} - {self.entity_id}"
