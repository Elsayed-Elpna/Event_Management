from django.db import models
from common.models import BaseModel
from django.conf import settings


# Create your models here.
class Reservation(BaseModel):
    class ReservationStatus(models.TextChoices):
        HELD = "HELD", "Held"
        CONFIRMED = "CONFIRMED", "Confirmed"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    ticket_type = models.ForeignKey(
        "events.TicketType",
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    quantity = models.PositiveIntegerField()
    expires_at = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=ReservationStatus.choices, default=ReservationStatus.HELD
    )
    reserved_unit_price = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.user.email} - {self.status}"
