from django.db import models
from django.core.exceptions import ValidationError
from common.models import BaseModel
from events.models.event import Event


class TicketType(BaseModel):
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="ticket_types"
    )
    name = models.CharField(max_length=255)
    price_cents = models.PositiveIntegerField()
    capacity = models.PositiveIntegerField()
    available_inventory = models.PositiveIntegerField()

    def clean(self):
        if self.available_inventory > self.capacity:
            raise ValidationError("Available inventory cannot be greater than capacity")

    def __str__(self):
        return f"{self.event.title} - {self.name}"
