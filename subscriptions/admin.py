from django.contrib import admin
from .models import Subscription

# Register your models here.


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount_cents", "status", "starts_at", "expires_at")
    list_select_related = ("user",)
    search_fields = ("user__email", "user__first_name", "user__last_name")
    list_filter = ("status",)
