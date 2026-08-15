from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from events.models import Event, TicketType
from events.models.event import EventStatus
from orders.service import create_order
from payments.models import Payment
from payments.services.order_payment_webhook_service import (
    process_successful_order_payment,
)
from reservations.services import create_reservation


class EarningAPITestCase(APITestCase):

    def setUp(self):
        self.organizer = User.objects.create_user(
            email="organizer@test.com",
            password="TestPassword123",
            is_event_maker=True,
        )

        self.buyer = User.objects.create_user(
            email="buyer@test.com",
            password="TestPassword123",
            is_event_maker=False,
        )

        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Django Conference",
            description="Backend event",
            location="Cairo",
            status=EventStatus.PUBLISHED,
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=4),
            hold_duration=10,
        )

        self.ticket_type = TicketType.objects.create(
            event=self.event,
            ticket_type=TicketType.TicketTypeChoice.REGULAR,
            price_cents=100000,
            capacity=100,
            available_inventory=100,
        )

    def make_paid_order(self, quantity=2, price_cents=100000):
        self.ticket_type.price_cents = price_cents
        self.ticket_type.save(update_fields=["price_cents"])

        reservation = create_reservation(
            user=self.buyer,
            validated_data={
                "ticket_type": self.ticket_type,
                "quantity": quantity,
            },
        )

        order = create_order(
            user=self.buyer,
            reservation_id=reservation.id,
            idempotency_key=uuid4(),
        )

        payment = Payment.objects.create(
            payment_type=Payment.PaymentType.ORDER,
            amount=order.total_price,
            status=Payment.PaymentStatus.PENDING,
        )

        order.payment = payment
        order.save(update_fields=["payment"])

        transaction_data = {
            "order": {
                "merchant_order_id": f"order-{order.id}-payment-{payment.id}",
            },
            "amount_cents": payment.amount,
            "id": 123456,
            "created_at": timezone.now().isoformat(),
        }

        process_successful_order_payment(transaction_data=transaction_data)

        order.refresh_from_db()

        return order

    def get_earnings(self):
        self.client.force_authenticate(user=self.organizer)
        return self.client.get("/api/earnings/")

    def test_organizer_sees_their_sales(self):
        order = self.make_paid_order(quantity=2)

        response = self.get_earnings()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["records"]), 1)

        record = response.data["records"][0]

        self.assertEqual(record["order_id"], order.id)
        self.assertEqual(record["event_title"], self.event.title)
        self.assertEqual(record["quantity"], 2)
        self.assertEqual(record["gross_amount"], order.total_price)
        self.assertEqual(
            record["net_amount"],
            order.total_price - order.platform_fee - order.payment_fee,
        )

    def test_organizer_only_sees_own_sales(self):
        other_organizer = User.objects.create_user(
            email="other-org@test.com",
            password="TestPassword123",
            is_event_maker=True,
        )

        self.make_paid_order(quantity=1)

        self.client.force_authenticate(user=other_organizer)

        response = self.client.get("/api/earnings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["records"]), 0)
        self.assertEqual(
            response.data["summary"]["all_time"]["total_tickets_sold"],
            0,
        )

    def test_summary_this_month_and_all_time(self):
        self.make_paid_order(quantity=2)

        response = self.get_earnings()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        summary = response.data["summary"]

        self.assertEqual(summary["this_month"]["total_orders"], 1)
        self.assertEqual(summary["this_month"]["total_tickets_sold"], 2)
        self.assertEqual(summary["this_month"]["gross_amount"], 200000)
        self.assertEqual(summary["this_month"]["net_amount"], 200000)

        self.assertEqual(summary["all_time"]["total_orders"], 1)
        self.assertEqual(summary["all_time"]["total_tickets_sold"], 2)

    def test_summary_excludes_refunded_orders(self):
        order = self.make_paid_order(quantity=2)

        earning = order.earning
        earning.gross_amount = 0
        earning.platform_fee = 0
        earning.payment_fee = 0
        earning.net_amount = 0
        earning.save()

        response = self.get_earnings()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        summary = response.data["summary"]["all_time"]

        self.assertEqual(summary["total_orders"], 0)
        self.assertEqual(summary["total_tickets_sold"], 0)
        self.assertEqual(summary["net_amount"], 0)

    def test_requires_auth(self):
        response = self.client.get("/api/earnings/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
