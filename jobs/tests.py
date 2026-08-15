from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from audit.models import AuditLog
from events.models import Event, TicketType
from events.models.event import EventStatus
from jobs.services.expiry_service import (
    expire_reservations,
    expire_subscriptions,
    fail_expired_orders,
    finish_events,
)
from orders.models import Order
from orders.service import create_order
from payments.models import Payment
from reservations.models import Reservation
from reservations.services import create_reservation
from subscriptions.models import Subscription, SubscriptionStatus


class BackgroundJobTestCase(TestCase):

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

    def make_expired_reservation(self, quantity=2):
        reservation = create_reservation(
            user=self.user,
            validated_data={
                "ticket_type": self.ticket_type,
                "quantity": quantity,
            },
        )

        reservation.expires_at = timezone.now() - timedelta(minutes=1)
        reservation.save(update_fields=["expires_at"])

        return reservation

    def make_pending_order(self, quantity=2):
        reservation = create_reservation(
            user=self.user,
            validated_data={
                "ticket_type": self.ticket_type,
                "quantity": quantity,
            },
        )

        order = create_order(
            user=self.user,
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

        reservation.expires_at = timezone.now() - timedelta(minutes=1)
        reservation.save(update_fields=["expires_at"])

        return reservation, order, payment

    # ---------------------------------
    # expire_subscriptions
    # ---------------------------------

    def test_expires_active_subscription_past_expiry(self):
        Subscription.objects.create(
            user=self.event_maker,
            amount_cents=100000,
            status=SubscriptionStatus.ACTIVE,
            starts_at=timezone.now() - timedelta(days=30),
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        count = expire_subscriptions()

        self.assertEqual(count, 1)

        self.event_maker.subscription.refresh_from_db()

        self.assertEqual(
            self.event_maker.subscription.status,
            SubscriptionStatus.EXPIRED,
        )

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.AuditAction.SUBSCRIPTION_EXPIRED,
                entity_id=self.event_maker.subscription.id,
            ).exists()
        )

    def test_does_not_expire_future_subscription(self):
        Subscription.objects.create(
            user=self.event_maker,
            amount_cents=100000,
            status=SubscriptionStatus.ACTIVE,
            starts_at=timezone.now() - timedelta(days=1),
            expires_at=timezone.now() + timedelta(days=1),
        )

        count = expire_subscriptions()

        self.assertEqual(count, 0)

        self.event_maker.subscription.refresh_from_db()

        self.assertEqual(
            self.event_maker.subscription.status,
            SubscriptionStatus.ACTIVE,
        )

    # ---------------------------------
    # finish_events
    # ---------------------------------

    def test_finishes_published_event_past_end(self):
        self.event.ends_at = timezone.now() - timedelta(minutes=1)
        self.event.save(update_fields=["ends_at"])

        count = finish_events()

        self.assertEqual(count, 1)

        self.event.refresh_from_db()

        self.assertEqual(self.event.status, EventStatus.FINISHED)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.AuditAction.EVENT_FINISHED,
                entity_id=self.event.id,
            ).exists()
        )

    def test_finishes_draft_event_past_end(self):
        self.event.status = EventStatus.DRAFT
        self.event.ends_at = timezone.now() - timedelta(minutes=1)
        self.event.save(update_fields=["status", "ends_at"])

        count = finish_events()

        self.assertEqual(count, 1)

        self.event.refresh_from_db()

        self.assertEqual(self.event.status, EventStatus.FINISHED)

    def test_does_not_finish_cancelled_event(self):
        self.event.status = EventStatus.CANCELLED
        self.event.ends_at = timezone.now() - timedelta(minutes=1)
        self.event.save(update_fields=["status", "ends_at"])

        count = finish_events()

        self.assertEqual(count, 0)

        self.event.refresh_from_db()

        self.assertEqual(self.event.status, EventStatus.CANCELLED)

    def test_does_not_finish_upcoming_event(self):
        count = finish_events()

        self.assertEqual(count, 0)

        self.event.refresh_from_db()

        self.assertEqual(self.event.status, EventStatus.PUBLISHED)

    # ---------------------------------
    # expire_reservations
    # ---------------------------------

    def test_expired_reservation_restores_inventory(self):
        reservation = self.make_expired_reservation(quantity=2)

        self.ticket_type.refresh_from_db()
        self.assertEqual(self.ticket_type.available_inventory, 98)

        count = expire_reservations()

        self.assertEqual(count, 1)

        reservation.refresh_from_db()
        self.ticket_type.refresh_from_db()

        self.assertEqual(reservation.status, Reservation.ReservationStatus.EXPIRED)
        self.assertEqual(self.ticket_type.available_inventory, 100)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.AuditAction.RESERVATION_EXPIRED,
                entity_id=reservation.id,
            ).exists()
        )

    def test_does_not_expire_unexpired_reservation(self):
        reservation = create_reservation(
            user=self.user,
            validated_data={
                "ticket_type": self.ticket_type,
                "quantity": 1,
            },
        )

        count = expire_reservations()

        self.assertEqual(count, 0)

        reservation.refresh_from_db()

        self.assertEqual(reservation.status, Reservation.ReservationStatus.HELD)

    # ---------------------------------
    # fail_expired_orders
    # ---------------------------------

    def test_fails_pending_order_of_expired_reservation(self):
        reservation, order, payment = self.make_pending_order(quantity=2)

        expire_reservations()
        count = fail_expired_orders()

        self.assertEqual(count, 1)

        order.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(order.status, Order.OrderStatus.FAILED)
        self.assertEqual(payment.status, Payment.PaymentStatus.FAILED)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.AuditAction.ORDER_FAILED,
                entity_id=order.id,
            ).exists()
        )

    def test_does_not_fail_paid_order(self):
        reservation, order, payment = self.make_pending_order(quantity=1)
        reservation.status = Reservation.ReservationStatus.CONFIRMED
        reservation.save(update_fields=["status"])

        order.status = Order.OrderStatus.PAID
        order.save(update_fields=["status"])

        count = fail_expired_orders()

        self.assertEqual(count, 0)

        order.refresh_from_db()

        self.assertEqual(order.status, Order.OrderStatus.PAID)
