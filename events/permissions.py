from rest_framework.permissions import BasePermission


class IsEventMaker(BasePermission):
    message = "Only event makers can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_event_maker
        )
