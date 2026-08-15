from datetime import timedelta
from uuid import uuid4

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from audit.models import AuditLog
from events.models import Event, TicketType
from events.models.event import EventStatus
from orders.models import Order
from reservations.models import Reservation
from reservations.services import create_reservation
from subscriptions.models import Subscription, SubscriptionStatus


class OrderAPITestCase(APITestCase):

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

    def make_reservation(self, quantity=2, user=None):
        reservation = create_reservation(
            user=user or self.user,
            validated_data={
                "ticket_type": self.ticket_type,
                "quantity": quantity,
            },
        )
        return reservation

    def create_order(self, reservation_id, idempotency_key=None):
        return self.client.post(
            "/api/orders/create/",
            {
                "reservation_id": reservation_id,
                "idempotency_key": str(idempotency_key or uuid4()),
            },
            format="json",
        )

    def test_create_order(self):
        reservation = self.make_reservation()

        response = self.create_order(reservation.id)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        order = Order.objects.get()

        self.assertEqual(order.user, self.user)
        self.assertEqual(order.reservation, reservation)
        self.assertEqual(order.quantity, reservation.quantity)
        self.assertEqual(order.unit_price, reservation.reserved_unit_price)
        self.assertEqual(
            order.total_price,
            reservation.quantity * reservation.reserved_unit_price,
        )
        self.assertEqual(order.status, Order.OrderStatus.PENDING)
        self.assertTrue(order.idempotency_key)

    def test_create_order_audit_log_created(self):
        reservation = self.make_reservation()

        self.create_order(reservation.id)

        audit = AuditLog.objects.get(action=AuditLog.AuditAction.ORDER_CREATED)

        self.assertEqual(audit.actor, self.user)
        self.assertEqual(audit.entity_type, "Order")
        self.assertEqual(audit.metadata["reservation_id"], reservation.id)

    def test_same_idempotency_key_returns_same_order(self):
        reservation = self.make_reservation()
        idempotency_key = uuid4()

        first_response = self.create_order(reservation.id, idempotency_key)
        second_response = self.create_order(reservation.id, idempotency_key)

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            second_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            first_response.data["id"],
            second_response.data["id"],
        )

        self.assertEqual(Order.objects.count(), 1)

    def test_idempotency_key_belongs_to_another_user(self):
        reservation = self.make_reservation()
        idempotency_key = uuid4()

        self.create_order(reservation.id, idempotency_key)

        other_user = User.objects.create_user(
            email="other@test.com",
            password="TestPassword123",
        )

        self.client.force_authenticate(user=other_user)

        response = self.create_order(reservation.id, idempotency_key)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cannot_create_order_for_other_users_reservation(self):
        other_user = User.objects.create_user(
            email="other@test.com",
            password="TestPassword123",
        )

        reservation = self.make_reservation(user=other_user)

        response = self.create_order(reservation.id)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cannot_create_order_for_non_held_reservation(self):
        reservation = self.make_reservation()

        reservation.status = Reservation.ReservationStatus.CANCELLED
        reservation.save(update_fields=["status"])

        response = self.create_order(reservation.id)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cannot_create_order_for_expired_reservation(self):
        reservation = self.make_reservation()

        reservation.expires_at = timezone.now() - timedelta(minutes=1)
        reservation.save(update_fields=["expires_at"])

        response = self.create_order(reservation.id)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_second_order_for_same_reservation_returns_existing(self):
        reservation = self.make_reservation()

        first_response = self.create_order(reservation.id)
        second_response = self.create_order(reservation.id)

        self.assertEqual(
            second_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            first_response.data["id"],
            second_response.data["id"],
        )

        self.assertEqual(Order.objects.count(), 1)

    def test_create_order_for_missing_reservation(self):
        response = self.create_order(99999)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_my_orders_lists_only_user_orders(self):
        reservation_one = self.make_reservation()
        reservation_two = self.make_reservation()

        self.create_order(reservation_one.id)
        self.create_order(reservation_two.id)

        other_user = User.objects.create_user(
            email="other@test.com",
            password="TestPassword123",
        )

        other_reservation = self.make_reservation(user=other_user)

        self.client.force_authenticate(user=other_user)
        self.create_order(other_reservation.id)

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/orders/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 2)
