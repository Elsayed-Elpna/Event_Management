from django.contrib import admin
from .models import Balance


@admin.register(Balance)
class BalanceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "organizer",
        "gross_amount",
        "platform_fee",
        "payment_fee",
        "net_amount",
    )
    list_select_related = ("order__reservation", "order__user")
    search_fields = (
        "organizer__email",
        "order__user__email",
        "order__user__first_name",
        "order__user__last_name",
    )
    list_filter = ("gross_amount", "platform_fee", "payment_fee", "net_amount")
