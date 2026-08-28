from django.test import TestCase

# Create your tests here.
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch
from uuid import uuid4

import requests

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from audit.models import AuditLog
from balance.models import Balance
from events.models import Event, TicketType
from events.models.event import EventStatus
from orders.models import Order
from orders.service import (
    create_order,
    _save_payment_intention,
)
from payments.models import Payment, Refund
from reservations.models import Reservation
from payments.services.order_payment_webhook_service import (
    process_successful_order_payment,
)
from payments.services.refund_service import (
    TransientProviderError,
    finalize_refund,
    process_order_refund,
)
from reservations.services import create_reservation
from subscriptions.models import Subscription, SubscriptionStatus


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
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
            starts_at=timezone.now() + timedelta(days=3),
            ends_at=timezone.now() + timedelta(days=3, hours=4),
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
            with self.captureOnCommitCallbacks(execute=True):
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

    def test_refund_zeroes_balance(self):
        order = self.make_paid_order()

        balance = Balance.objects.get(order=order)
        self.assertEqual(balance.gross_amount, order.total_price)

        self.client.force_authenticate(user=self.event_maker)

        self.refund(order.id)

        balance.refresh_from_db()

        self.assertEqual(balance.gross_amount, 0)
        self.assertEqual(balance.platform_fee, 0)
        self.assertEqual(balance.payment_fee, 0)
        self.assertEqual(balance.net_amount, 0)

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

    def test_refund_response_reports_pending(self):
        order = self.make_paid_order()

        self.client.force_authenticate(user=self.event_maker)

        with patch(
            "payments.services.paymob_service.PaymobService.create_refund",
            return_value={},
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    f"/api/orders/{order.id}/refund/",
                    {"reason": "Async check"},
                    format="json",
                )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["status"],
            Refund.RefundStatus.PENDING,
        )


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class RefundProviderFailureTestCase(RefundAPITestCase):
    def test_provider_rejection_marks_refund_failed(self):
        order = self.make_paid_order(quantity=2)

        rejected_response = requests.Response()
        rejected_response.status_code = 400

        with patch(
            "payments.services.paymob_service.PaymobService.create_refund",
            side_effect=requests.HTTPError(
                "400 Client Error",
                response=rejected_response,
            ),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    f"/api/orders/{order.id}/refund/",
                    {"reason": "Rejected"},
                    format="json",
                )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        refund = Refund.objects.get(order=order)

        self.assertEqual(refund.status, Refund.RefundStatus.FAILED)
        self.assertIsNone(refund.refunded_at)

        order.refresh_from_db()
        order.payment.refresh_from_db()
        self.ticket_type.refresh_from_db()

        self.assertEqual(order.status, Order.OrderStatus.PAID)
        self.assertEqual(
            order.payment.status,
            Payment.PaymentStatus.SUCCESS,
        )
        self.assertEqual(self.ticket_type.available_inventory, 98)

        balance = Balance.objects.get(order=order)
        self.assertEqual(balance.gross_amount, order.total_price)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.AuditAction.REFUND_CREATED,
                entity_id=order.id,
                reason__startswith="Refund failed before completion.",
            ).exists()
        )

    def test_transient_provider_error_keeps_refund_pending(self):
        order = self.make_paid_order()

        refund = process_order_refund(
            user=self.event_maker,
            order_id=order.id,
            reason="Transient test",
        )

        with patch(
            "payments.services.paymob_service.PaymobService.create_refund",
            side_effect=requests.ConnectionError("connection dropped"),
        ):
            with self.assertRaises(TransientProviderError):
                finalize_refund(refund_id=refund.id)

        refund.refresh_from_db()

        self.assertEqual(refund.status, Refund.RefundStatus.PENDING)

        order.refresh_from_db()

        self.assertEqual(order.status, Order.OrderStatus.PAID)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class OrderPaymentAPITestCase(APITestCase):

    def setUp(self):
        self.buyer = User.objects.create_user(
            email="buyer@test.com",
            password="TestPassword123",
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
            starts_at=timezone.now() + timedelta(days=3),
            ends_at=timezone.now() + timedelta(days=3, hours=4),
            hold_duration=10,
        )

        self.ticket_type = TicketType.objects.create(
            event=self.event,
            ticket_type=TicketType.TicketTypeChoice.REGULAR,
            price_cents=100000,
            capacity=100,
            available_inventory=100,
        )

        self.client.force_authenticate(user=self.buyer)

    def make_pending_order(self, quantity=1):
        reservation = create_reservation(
            user=self.buyer,
            validated_data={
                "ticket_type": self.ticket_type,
                "quantity": quantity,
            },
        )

        return create_order(
            user=self.buyer,
            reservation_id=reservation.id,
            idempotency_key=uuid4(),
        )

    def pay(self, order_id, intention_response=None, side_effect=None):
        patcher = patch(
            "payments.services.paymob_service.PaymobService.create_order_intention",
            return_value=intention_response or {},
            side_effect=side_effect,
        )

        mocked = patcher.start()
        response = self.client.post(f"/api/orders/{order_id}/payment/")
        patcher.stop()

        return response, mocked

    def test_payment_initiation_success(self):
        order = self.make_pending_order()

        response, mocked = self.pay(
            order.id,
            intention_response={"id": "int-1", "client_secret": "secret-abc"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["client_secret"],
            "secret-abc",
        )

        self.assertIn(
            "secret-abc",
            response.data["checkout_url"],
        )

        payment = Payment.objects.get(order=order)

        self.assertEqual(
            str(payment.provider_reference),
            "int-1",
        )

        self.assertEqual(
            payment.client_secret,
            "secret-abc",
        )

        mocked.assert_called_once()

    def test_payment_initiation_is_idempotent(self):
        order = self.make_pending_order()

        first_response, _ = self.pay(
            order.id,
            intention_response={"id": "int-1", "client_secret": "secret-abc"},
        )

        second_response, mocked = self.pay(
            order.id,
            intention_response={"id": "int-2", "client_secret": "secret-xyz"},
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            second_response.data["client_secret"],
            "secret-abc",
        )

        mocked.assert_not_called()

    def test_provider_outage_keeps_payment_retryable(self):
        order = self.make_pending_order()

        response, _ = self.pay(
            order.id,
            side_effect=requests.ConnectionError("paymob unreachable"),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        payment = Payment.objects.get(order=order)

        self.assertEqual(payment.status, Payment.PaymentStatus.PENDING)
        self.assertIsNone(payment.provider_reference)
        self.assertIsNone(payment.client_secret)

        retry_response, _ = self.pay(
            order.id,
            intention_response={"id": "int-9", "client_secret": "secret-retry"},
        )

        self.assertEqual(retry_response.status_code, status.HTTP_200_OK)

        payment.refresh_from_db()

        self.assertEqual(payment.client_secret, "secret-retry")

    def test_first_writer_wins_on_intention_persistence(self):
        order = self.make_pending_order()

        winner = Payment.objects.create(
            payment_type=Payment.PaymentType.ORDER,
            amount=order.total_price,
            status=Payment.PaymentStatus.PENDING,
            provider_reference="winner-ref",
            client_secret="winner-secret",
        )

        order.payment = winner
        order.save(update_fields=["payment"])

        result = _save_payment_intention(
            order=order,
            provider_reference="loser-ref",
            client_secret="loser-secret",
        )

        self.assertEqual(result["client_secret"], "winner-secret")

        winner.refresh_from_db()

        self.assertEqual(winner.provider_reference, "winner-ref")
        self.assertEqual(winner.client_secret, "winner-secret")


class OrderWebhookGuardTestCase(APITestCase):
    """A stale, duplicate, or unprocessable payment webhook must be acknowledged
    with 2xx and must never mark a payment as successful for a reservation
    that can no longer be confirmed."""

    def setUp(self):
        self.buyer = User.objects.create_user(
            email="guardbuyer@test.com",
            password="TestPassword123",
        )

        self.event_maker = User.objects.create_user(
            email="guardmaker@test.com",
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
            title="Guard Conference",
            description="Webhook guard event",
            location="Cairo",
            status=EventStatus.PUBLISHED,
            starts_at=timezone.now() + timedelta(days=3),
            ends_at=timezone.now() + timedelta(days=3, hours=4),
            hold_duration=10,
        )

        self.ticket_type = TicketType.objects.create(
            event=self.event,
            ticket_type=TicketType.TicketTypeChoice.REGULAR,
            price_cents=100000,
            capacity=100,
            available_inventory=100,
        )

        self.client.force_authenticate(user=self.buyer)

    def make_pending_order(self, quantity=1):
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

        return order

    def post_webhook(self, order, payment, transaction_id=991122):
        payload = {
            "obj": {
                "order": {
                    "merchant_order_id": (
                        f"order-{order.id}-payment-{payment.id}"
                    ),
                },
                "amount_cents": order.total_price,
                "id": transaction_id,
                "created_at": timezone.now().isoformat(),
                "success": True,
            }
        }

        with patch(
            "payments.services.paymob_service.PaymobService.verify_transaction_hmac",
            return_value=True,
        ):
            return self.client.post(
                "/api/payments/webhook/?hmac=test-hmac",
                payload,
                format="json",
            )

    def test_webhook_processed_for_valid_reservation(self):
        order = self.make_pending_order()

        response = self.post_webhook(order, order.payment)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "payment_processed")
        self.assertEqual(response.data["order_id"], order.id)

        order.refresh_from_db()
        order.reservation.refresh_from_db()
        order.payment.refresh_from_db()

        self.assertEqual(order.status, Order.OrderStatus.PAID)
        self.assertEqual(
            order.payment.status,
            Payment.PaymentStatus.SUCCESS,
        )
        self.assertEqual(order.payment.provider_transaction_id, "991122")
        self.assertEqual(
            order.reservation.status,
            Reservation.ReservationStatus.CONFIRMED,
        )
        self.assertTrue(Balance.objects.filter(order=order).exists())

    def test_duplicate_webhook_is_idempotent(self):
        order = self.make_pending_order()

        first = self.post_webhook(order, order.payment)
        second = self.post_webhook(order, order.payment)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data["status"], "payment_processed")

        self.assertEqual(Balance.objects.filter(order=order).count(), 1)
        self.assertEqual(
            AuditLog.objects.filter(
                action=AuditLog.AuditAction.ORDER_PAID,
                entity_id=order.id,
            ).count(),
            1,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.PAID)

    def test_webhook_ignored_for_expired_reservation(self):
        order = self.make_pending_order()

        reservation = order.reservation
        reservation.status = Reservation.ReservationStatus.EXPIRED
        reservation.expires_at = timezone.now() - timedelta(minutes=1)
        reservation.save(update_fields=["status", "expires_at"])

        response = self.post_webhook(order, order.payment)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ignored")
        self.assertTrue(response.data["reason"])

        order.refresh_from_db()
        order.payment.refresh_from_db()

        self.assertEqual(order.status, Order.OrderStatus.PENDING)
        self.assertEqual(order.payment.status, Payment.PaymentStatus.PENDING)
        self.assertIsNone(order.payment.provider_transaction_id)

    def test_webhook_ignored_for_cancelled_reservation(self):
        order = self.make_pending_order()

        reservation = order.reservation
        reservation.status = Reservation.ReservationStatus.CANCELLED
        reservation.save(update_fields=["status"])

        response = self.post_webhook(order, order.payment)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ignored")

        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.PENDING)
        self.assertEqual(
            order.payment.status,
            Payment.PaymentStatus.PENDING,
        )

    def test_webhook_ignored_after_refund(self):
        order = self.make_pending_order()

        # Process the first (successful) payment.
        self.post_webhook(order, order.payment)

        # Emulate the outcome of a completed refund.
        order.refresh_from_db()
        order.status = Order.OrderStatus.REFUNDED
        order.save(update_fields=["status"])
        order.payment.status = Payment.PaymentStatus.REFUNDED
        order.payment.save(update_fields=["status"])

        # A stale retry of the success webhook must not flip it back.
        response = self.post_webhook(order, order.payment)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ignored")

        order.refresh_from_db()
        order.payment.refresh_from_db()

        self.assertEqual(order.status, Order.OrderStatus.REFUNDED)
        self.assertEqual(
            order.payment.status,
            Payment.PaymentStatus.REFUNDED,
        )


class SubscriptionWebhookTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="subwebhook@test.com",
            password="TestPassword123",
            is_event_maker=False,
        )

        self.subscription = Subscription.objects.create(
            user=self.user,
            amount_cents=100000,
            status=SubscriptionStatus.PENDING,
        )

        self.payment = Payment.objects.create(
            payment_type=Payment.PaymentType.SUBSCRIPTION,
            amount=100000,
            status=Payment.PaymentStatus.PENDING,
        )

        self.subscription.payment = self.payment
        self.subscription.save(update_fields=["payment"])

    def test_process_successful_subscription_payment(self):
        from payments.services.payments_webhook_service import (
            process_successful_payment,
        )

        transaction_data = {
            "order": {
                "merchant_order_id": (
                    f"subscription-{self.subscription.id}-payment-{self.payment.id}"
                ),
            },
            "amount_cents": self.payment.amount,
            "id": 777888,
            "created_at": "2026-01-01T10:00:00.000000",
            "success": True,
        }

        subscription = process_successful_payment(
            transaction_data=transaction_data,
        )

        subscription.refresh_from_db()
        subscription.payment.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)
        self.assertTrue(self.user.is_event_maker)
        self.assertEqual(
            subscription.payment.status,
            Payment.PaymentStatus.SUCCESS,
        )
        self.assertEqual(
            str(subscription.payment.provider_transaction_id),
            "777888",
        )

        self.assertTrue(timezone.is_aware(subscription.payment.paid_at))
        self.assertEqual(
            subscription.payment.paid_at,
            datetime(2026, 1, 1, 10, 0, tzinfo=dt_timezone.utc),
        )
        self.assertEqual(
            subscription.starts_at,
            datetime(2026, 1, 1, 10, 0, tzinfo=dt_timezone.utc),
        )
        self.assertEqual(
            subscription.expires_at,
            datetime(2026, 1, 31, 10, 0, tzinfo=dt_timezone.utc),
        )


class RefundCutoffTestCase(RefundAPITestCase):
    """
    Refunds are blocked for everyone (buyers, organizers, staff) within
    REFUND_CUTOFF_HOURS of the event start, and after the event started.
    """

    def _set_event_start(self, **delta):
        self.event.starts_at = timezone.now() + timedelta(**delta)
        self.event.ends_at = self.event.starts_at + timedelta(hours=4)
        self.event.save(
            update_fields=[
                "starts_at",
                "ends_at",
                "updated_at",
            ]
        )

    def test_buyer_cannot_refund_inside_cutoff_window(self):
        self._set_event_start(days=1)

        order = self.make_paid_order()

        response = self.refund(order.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Refunds are closed", response.data["detail"])
        self.assertFalse(Refund.objects.filter(order_id=order.id).exists())

    def test_buyer_cannot_refund_after_event_started(self):
        self._set_event_start(hours=-1)

        order = self.make_paid_order()

        response = self.refund(order.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Refunds are closed", response.data["detail"])

    def test_buyer_can_refund_outside_cutoff_window(self):
        self._set_event_start(days=3, hours=1)

        order = self.make_paid_order()

        response = self.refund(order.id)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_organizer_also_blocked_inside_cutoff_window(self):
        self._set_event_start(days=1)

        order = self.make_paid_order(user=self.user)

        self.client.force_authenticate(user=self.event_maker)

        response = self.refund(order.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Refunds are closed", response.data["detail"])

    def test_successful_refund_cancels_reservation(self):
        order = self.make_paid_order()

        response = self.refund(order.id)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        order.reservation.refresh_from_db()

        self.assertEqual(
            order.reservation.status,
            Reservation.ReservationStatus.CANCELLED,
        )
        self.assertTrue(
            Refund.objects.filter(
                order_id=order.id,
                status=Refund.RefundStatus.SUCCESS,
            ).exists()
        )
