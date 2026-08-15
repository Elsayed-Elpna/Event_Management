from django.test import TestCase

# Create your tests here.
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from audit.models import AuditLog
from earnings.models import Earning
from events.models import Event, TicketType
from events.models.event import EventStatus
from orders.models import Order
from orders.service import create_order
from payments.models import Payment, Refund
from payments.services.order_payment_webhook_service import (
    process_successful_order_payment,
)
from reservations.services import create_reservation
from subscriptions.models import Subscription, SubscriptionStatus


class RefundAPITestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="user@test.com",
            password="TestPassword123",
            is_event_maker=False,
        )

        self.event_maker = User.objects.create_user(
            email="maker@test.com",
            password="TestPassword123",
            is_event_maker=True,
        )

        Subscription.objects.create(
            user=self.event_maker,
            amount_cents=100000,
            status=SubscriptionStatus.ACTIVE,
        )

        self.event = Event.objects.create(
            organizer=self.event_maker,
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

        self.client.force_authenticate(user=self.user)

    def make_paid_order(self, quantity=2, user=None):
        reservation = create_reservation(
            user=user or self.user,
            validated_data={
                "ticket_type": self.ticket_type,
                "quantity": quantity,
            },
        )

        order = create_order(
            user=user or self.user,
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

    def refund(self, order_id, reason="Test refund"):
        with patch(
            "payments.services.paymob_service.PaymobService.create_refund",
            return_value={
                "success": True,
                "refund_id": "sim-refund",
            },
        ):
            return self.client.post(
                f"/api/orders/{order_id}/refund/",
                {"reason": reason},
                format="json",
            )

    def test_organizer_can_refund_paid_order(self):
        order = self.make_paid_order()

        self.client.force_authenticate(user=self.event_maker)

        response = self.refund(order.id)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        order.refresh_from_db()
        order.payment.refresh_from_db()
        self.ticket_type.refresh_from_db()

        self.assertEqual(order.status, Order.OrderStatus.REFUNDED)
        self.assertEqual(
            order.payment.status,
            Payment.PaymentStatus.REFUNDED,
        )

        refund = Refund.objects.get()
        self.assertEqual(refund.order, order)
        self.assertEqual(refund.status, Refund.RefundStatus.SUCCESS)
        self.assertIsNotNone(refund.refunded_at)

    def test_buyer_can_refund_own_order(self):
        order = self.make_paid_order()

        response = self.refund(order.id)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_refund_restores_inventory(self):
        order = self.make_paid_order(quantity=2)

        self.ticket_type.refresh_from_db()
        self.assertEqual(self.ticket_type.available_inventory, 98)

        self.client.force_authenticate(user=self.event_maker)

        self.refund(order.id)

        self.ticket_type.refresh_from_db()

        self.assertEqual(self.ticket_type.available_inventory, 100)

    def test_refund_zeroes_earning(self):
        order = self.make_paid_order()

        earning = Earning.objects.get(order=order)
        self.assertEqual(earning.gross_amount, order.total_price)

        self.client.force_authenticate(user=self.event_maker)

        self.refund(order.id)

        earning.refresh_from_db()

        self.assertEqual(earning.gross_amount, 0)
        self.assertEqual(earning.platform_fee, 0)
        self.assertEqual(earning.payment_fee, 0)
        self.assertEqual(earning.net_amount, 0)

    def test_refund_creates_audit_logs(self):
        order = self.make_paid_order()

        self.client.force_authenticate(user=self.event_maker)

        self.refund(order.id)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.AuditAction.REFUND_CREATED,
                entity_id=order.id,
            ).exists()
        )

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.AuditAction.INVENTORY_UPDATED,
                entity_id=self.ticket_type.id,
            ).exists()
        )

    def test_cannot_refund_another_users_order(self):
        other_user = User.objects.create_user(
            email="other@test.com",
            password="TestPassword123",
        )

        order = self.make_paid_order()

        self.client.force_authenticate(user=other_user)

        response = self.refund(order.id)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cannot_refund_non_paid_order(self):
        reservation = create_reservation(
            user=self.user,
            validated_data={
                "ticket_type": self.ticket_type,
                "quantity": 1,
            },
        )

        order = create_order(
            user=self.user,
            reservation_id=reservation.id,
            idempotency_key=uuid4(),
        )

        self.client.force_authenticate(user=self.event_maker)

        response = self.refund(order.id)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cannot_refund_order_twice(self):
        order = self.make_paid_order()

        self.client.force_authenticate(user=self.event_maker)

        first_response = self.refund(order.id)

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        second_response = self.refund(order.id)

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_refund_missing_order(self):
        response = self.refund(99999)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
