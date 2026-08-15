from django.db import models
from django.core.exceptions import ValidationError
from common.models import BaseModel
from events.models.event import Event


class TicketType(BaseModel):
    class TicketTypeChoice(models.TextChoices):
        REGULAR = "REGULAR", "Regular"
        VIP = "VIP", "VIP"

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="ticket_types"
    )

    ticket_type = models.CharField(
        max_length=20,
        choices=TicketTypeChoice.choices,
    )

    price_cents = models.PositiveIntegerField()
    capacity = models.PositiveIntegerField()
    available_inventory = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", "ticket_type"],
                name="event_ticket_type_unique",
            )
        ]

    def clean(self):
        if self.available_inventory > self.capacity:
            raise ValidationError("Available inventory cannot be greater than capacity")

    def __str__(self):
        return f"{self.event.title} - {self.ticket_type}"
