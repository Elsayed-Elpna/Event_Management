from django.contrib import admin

from .models import User

# Register your models here.


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "email",
        "first_name",
        "last_name",
        "is_event_maker",
        "is_active",
    )

    search_fields = ("email", "first_name", "last_name")

    list_filter = ("is_event_maker", "is_active")
