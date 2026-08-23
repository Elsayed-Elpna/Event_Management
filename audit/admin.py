from django.contrib import admin

from .models import AuditLog

# Register your models here.


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("actor", "action", "entity_type", "entity_id", "reason")
    list_select_related = ("actor",)
    search_fields = ("actor__email", "actor__first_name", "actor__last_name")
    list_filter = ("action", "entity_type")
