from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from common.models import BaseModel

# Create your models here.


class EventStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    CANCELLED = "CANCELLED", "Cancelled"
    FINISHED = "FINISHED", "Finished"


class Event(BaseModel):
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.DRAFT,
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    hold_duration = models.PositiveSmallIntegerField(default=10)

    def clean(self):
        if self.starts_at > self.ends_at:
            raise ValidationError("Start date must be before end date")

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return self.title
