from django.conf import settings
from django.db import connection
from redis import Redis
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    checks = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"

    try:
        client = Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        client.close()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"

    healthy = all(v == "ok" for v in checks.values())
    checks["status"] = "ok" if healthy else "error"
    return Response(checks, status=200 if healthy else 503)
