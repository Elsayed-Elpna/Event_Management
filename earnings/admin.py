from django.contrib import admin
from .models import Earning

# Register your models here.


@admin.register(Earning)
class EarningsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "gross_amount",
        "platform_fee",
        "payment_fee",
        "net_amount",
    )
    search_fields = (
        "order__user__email",
        "order__user__first_name",
        "order__user__last_name",
    )
    list_filter = ("gross_amount", "platform_fee", "payment_fee", "net_amount")
