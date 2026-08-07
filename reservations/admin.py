from django.contrib import admin
from .models import Reservation

# Register your models here.


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "ticket_type", "quantity", "expires_at", "status")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    list_filter = ("status",)
