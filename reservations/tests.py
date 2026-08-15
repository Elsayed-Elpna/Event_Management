from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from events.models import Event, TicketType
from events.models.event import EventStatus
from reservations.models import Reservation
from subscriptions.models import Subscription, SubscriptionStatus


class ReservationAPITestCase(APITestCase):

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

    def test_create_reservation(self):
        response = self.client.post(
            "/api/reservations/",
            {
                "ticket_type": self.ticket_type.id,
                "quantity": 2,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        reservation = Reservation.objects.get()

        self.assertEqual(reservation.user, self.user)

        self.assertEqual(
            reservation.status,
            Reservation.ReservationStatus.HELD,
        )

        self.assertEqual(
            reservation.quantity,
            2,
        )

        self.assertEqual(
            reservation.reserved_unit_price,
            100000,
        )

        self.ticket_type.refresh_from_db()

        self.assertEqual(
            self.ticket_type.available_inventory,
            98,
        )

    def test_reservation_keeps_price_snapshot(self):
        response = self.client.post(
            "/api/reservations/",
            {
                "ticket_type": self.ticket_type.id,
                "quantity": 2,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        reservation = Reservation.objects.get()

        self.ticket_type.price_cents = 150000
        self.ticket_type.save(update_fields=["price_cents"])

        reservation.refresh_from_db()

        self.assertEqual(
            reservation.reserved_unit_price,
            100000,
        )

    def test_cannot_reserve_more_than_inventory(self):
        self.ticket_type.available_inventory = 2
        self.ticket_type.save(update_fields=["available_inventory"])

        response = self.client.post(
            "/api/reservations/",
            {
                "ticket_type": self.ticket_type.id,
                "quantity": 3,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Reservation.objects.count(),
            0,
        )

        self.ticket_type.refresh_from_db()

        self.assertEqual(
            self.ticket_type.available_inventory,
            2,
        )

    def test_quantity_must_be_positive(self):
        response = self.client.post(
            "/api/reservations/",
            {
                "ticket_type": self.ticket_type.id,
                "quantity": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cannot_reserve_draft_event(self):
        self.event.status = EventStatus.DRAFT
        self.event.save(update_fields=["status"])

        response = self.client.post(
            "/api/reservations/",
            {
                "ticket_type": self.ticket_type.id,
                "quantity": 1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cannot_reserve_ended_event(self):
        self.event.ends_at = timezone.now() - timedelta(minutes=1)
        self.event.save(update_fields=["ends_at"])

        response = self.client.post(
            "/api/reservations/",
            {
                "ticket_type": self.ticket_type.id,
                "quantity": 1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_user_only_sees_own_reservations(self):
        other_user = User.objects.create_user(
            email="other@test.com",
            password="TestPassword123",
        )

        Reservation.objects.create(
            user=other_user,
            ticket_type=self.ticket_type,
            quantity=1,
            expires_at=timezone.now() + timedelta(minutes=10),
            status=Reservation.ReservationStatus.HELD,
            reserved_unit_price=100000,
        )

        response = self.client.get("/api/reservations/me/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            0,
        )

    def test_cancel_reservation_restores_inventory(self):
        reservation = Reservation.objects.create(
            user=self.user,
            ticket_type=self.ticket_type,
            quantity=3,
            expires_at=timezone.now() + timedelta(minutes=10),
            status=Reservation.ReservationStatus.HELD,
            reserved_unit_price=100000,
        )

        self.ticket_type.available_inventory = 97
        self.ticket_type.save(update_fields=["available_inventory"])

        response = self.client.post(f"/api/reservations/{reservation.id}/cancel/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        reservation.refresh_from_db()
        self.ticket_type.refresh_from_db()

        self.assertEqual(
            reservation.status,
            Reservation.ReservationStatus.CANCELLED,
        )

        self.assertEqual(
            self.ticket_type.available_inventory,
            100,
        )

    def test_cannot_cancel_other_users_reservation(self):
        other_user = User.objects.create_user(
            email="other@test.com",
            password="TestPassword123",
        )

        reservation = Reservation.objects.create(
            user=other_user,
            ticket_type=self.ticket_type,
            quantity=2,
            expires_at=timezone.now() + timedelta(minutes=10),
            status=Reservation.ReservationStatus.HELD,
            reserved_unit_price=100000,
        )

        response = self.client.post(f"/api/reservations/{reservation.id}/cancel/")

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        reservation.refresh_from_db()

        self.assertEqual(
            reservation.status,
            Reservation.ReservationStatus.HELD,
        )

    def test_cannot_cancel_reservation_twice(self):
        reservation = Reservation.objects.create(
            user=self.user,
            ticket_type=self.ticket_type,
            quantity=2,
            expires_at=timezone.now() + timedelta(minutes=10),
            status=Reservation.ReservationStatus.HELD,
            reserved_unit_price=100000,
        )

        self.ticket_type.available_inventory = 98
        self.ticket_type.save(update_fields=["available_inventory"])

        first_response = self.client.post(f"/api/reservations/{reservation.id}/cancel/")

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        second_response = self.client.post(
            f"/api/reservations/{reservation.id}/cancel/"
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.ticket_type.refresh_from_db()

        self.assertEqual(
            self.ticket_type.available_inventory,
            100,
        )

    def test_cannot_cancel_expired_reservation(self):
        reservation = Reservation.objects.create(
            user=self.user,
            ticket_type=self.ticket_type,
            quantity=2,
            expires_at=timezone.now() - timedelta(minutes=1),
            status=Reservation.ReservationStatus.EXPIRED,
            reserved_unit_price=100000,
        )

        response = self.client.post(f"/api/reservations/{reservation.id}/cancel/")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cannot_cancel_confirmed_reservation(self):
      reservation = Reservation.objects.create(
          user=self.user,
          ticket_type=self.ticket_type,
          quantity=2,
          expires_at=timezone.now() + timedelta(minutes=10),
          status=Reservation.ReservationStatus.CONFIRMED,
          reserved_unit_price=100000,
      )

      response = self.client.post(
          f"/api/reservations/{reservation.id}/cancel/"
      )

      self.assertEqual(
          response.status_code,
          status.HTTP_400_BAD_REQUEST,
      )
