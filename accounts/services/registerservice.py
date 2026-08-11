from django.db import transaction
from audit.models import AuditLog
from django.contrib.auth import get_user_model


@transaction.atomic
def register_user(*, validated_data):
    validated_data.pop("confirm_password")
    password = validated_data.pop("password")
    user = get_user_model()(**validated_data)
    user.set_password(password)
    user.save()
    AuditLog.objects.create(
        actor=user,
        action=AuditLog.AuditAction.USER_REGISTERED,
        entity_type="User",
        entity_id=user.id,
        reason="New User Registered",
    )
    return user
