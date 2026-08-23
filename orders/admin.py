from django.contrib import admin
from .models import Order

# Register your models here.


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "reservation", "quantity", "total_price", "status")
    list_select_related = ("user", "reservation__user")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    list_filter = ("status",)
