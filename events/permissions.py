from rest_framework.permissions import BasePermission


class IsEventMaker(BasePermission):
    message = "Only event makers can create events."

    def has_permission(self, request, view):
        return request.user.is_authenticated
