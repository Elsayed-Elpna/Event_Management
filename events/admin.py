from django.contrib import admin

from .models import Event, TicketType

# Register your models here.


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "starts_at",
        "ends_at",
        "hold_duration",
        "status",
    )
    list_filter = ("status",)

    search_fields = (
        "title",
        "organizer__email",
    )


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ticket_type",
        "event",
        "price_cents",
        "capacity",
        "available_inventory",
    )
    list_select_related = ("event",)

    search_fields = (
        "event__title",
        "event__organizer__email",
    )
