from django.db.models import Count, Sum
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Balance
from .serializers import BalanceRecordSerializer


class MyBalanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _summary(self, queryset):
        aggregated = queryset.aggregate(
            total_orders=Count("id"),
            total_tickets_sold=Sum("order__quantity"),
            gross_amount=Sum("gross_amount"),
            platform_fee=Sum("platform_fee"),
            payment_fee=Sum("payment_fee"),
            net_amount=Sum("net_amount"),
        )

        return {
            "total_orders": aggregated["total_orders"],
            "total_tickets_sold": aggregated["total_tickets_sold"] or 0,
            "gross_amount": aggregated["gross_amount"] or 0,
            "platform_fee": aggregated["platform_fee"] or 0,
            "payment_fee": aggregated["payment_fee"] or 0,
            "net_amount": aggregated["net_amount"] or 0,
        }

    def get(self, request):
        base_queryset = Balance.objects.filter(organizer=request.user)

        paid_queryset = base_queryset.exclude(gross_amount=0)

        now = timezone.now()

        month_start = now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        records = (
            paid_queryset.select_related(
                "order",
                "order__payment",
                "order__refund",
                "order__reservation",
                "order__reservation__ticket_type",
                "order__reservation__ticket_type__event",
            )
            .order_by("-created_at")
        )

        summary = {
            "this_month": self._summary(
                paid_queryset.filter(created_at__gte=month_start)
            ),
            "all_time": self._summary(paid_queryset),
        }

        return Response(
            {
                "summary": summary,
                "records": BalanceRecordSerializer(records, many=True).data,
            },
            status=status.HTTP_200_OK,
        )
