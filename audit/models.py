from django.db import models
from django.conf import settings

from common.models import BaseModel

# Create your models here.


class AuditLog(BaseModel):
    class AuditAction(models.TextChoices):
        EVENT_CREATED = "EVENT_CREATED", "Event Created"
        EVENT_PUBLISHED = "EVENT_PUBLISHED", "Event Published"

        TICKET_TYPE_CREATED = "TICKET_TYPE_CREATED", "Ticket Type Created"
        INVENTORY_UPDATED = "INVENTORY_UPDATED", "Inventory Updated"

        RESERVATION_CREATED = "RESERVATION_CREATED", "Reservation Created"
        RESERVATION_EXPIRED = "RESERVATION_EXPIRED", "Reservation Expired"
        RESERVATION_CANCELLED = (
            "RESERVATION_CANCELLED",
            "Reservation Cancelled",
        )

        ORDER_CREATED = "ORDER_CREATED", "Order Created"
        ORDER_PAID = "ORDER_PAID", "Order Paid"
        ORDER_FAILED = "ORDER_FAILED", "Order Failed"
        EARNING_CREATED = "EARNING_CREATED", "Earning Created"

        REFUND_CREATED = "REFUND_CREATED", "Refund Created"

        EVENT_FINISHED = "EVENT_FINISHED", "Event Finished"

        SUBSCRIPTION_EXPIRED = "SUBSCRIPTION_EXPIRED", "Subscription Expired"

        USER_REGISTERED = "USER_REGISTERED", "User Registered"

        PAYMENT_SUCCESS = "PAYMENT_SUCCESS", "Payment Success"
        SUBSCRIPTION_ACTIVATED = "SUBSCRIPTION_ACTIVATED", "Subscription Activated"

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
        return f"{self.actor_id} - {self.action} - {self.entity_type} - {self.entity_id}"
