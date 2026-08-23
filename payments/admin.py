from django.contrib import admin
from .models import Payment, Refund

# Register your models here.


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "amount", "status")
    list_select_related = ("order__reservation", "order__user")
    search_fields = (
        "order__user__email",
        "order__user__first_name",
        "order__user__last_name",
    )
    list_filter = ("status",)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "reason", "status")
    list_select_related = ("order__reservation", "order__user")
    search_fields = (
        "order__user__email",
        "order__user__first_name",
        "order__user__last_name",
    )
    list_filter = ("status",)
