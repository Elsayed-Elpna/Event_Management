from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from subscriptions.models import Subscription, SubscriptionStatus
from events.models import Event, TicketType
from events.models.event import EventStatus


class EventAPITestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="maker@test.com",
            password="TestPassword123",
            is_event_maker=True,
        )

        Subscription.objects.create(
            user=self.user,
            amount_cents=100000,
            status=SubscriptionStatus.ACTIVE,
            starts_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
        )

        self.client.force_authenticate(user=self.user)

        self.event_data = {
            "title": "Django Conference",
            "description": "Backend event",
            "location": "Cairo",
            "starts_at": "2026-09-01T18:00:00Z",
            "ends_at": "2026-09-01T22:00:00Z",
            "hold_duration": 10,
        }

    def test_create_event(self):
        response = self.client.post(
            "/api/events/",
            self.event_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            Event.objects.count(),
            1,
        )

        event = Event.objects.first()

        self.assertEqual(
            event.organizer,
            self.user,
        )

        self.assertEqual(
            event.status,
            EventStatus.DRAFT,
        )

    def test_create_event_without_subscription(self):
        user = User.objects.create_user(
            email="normal@test.com",
            password="TestPassword123",
            is_event_maker=True,
        )

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/events/",
            self.event_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_list_events_for_event_maker(self):
        Event.objects.create(
            organizer=self.user,
            title="My Event",
            description="Event",
            location="Cairo",
            status=EventStatus.DRAFT,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=2),
            hold_duration=10,
        )

        response = self.client.get("/api/events/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

    def test_normal_user_sees_published_events_only(self):
        published_event = Event.objects.create(
            organizer=self.user,
            title="Published Event",
            description="Event",
            location="Cairo",
            status=EventStatus.PUBLISHED,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=2),
            hold_duration=10,
        )

        Event.objects.create(
            organizer=self.user,
            title="Draft Event",
            description="Event",
            location="Cairo",
            status=EventStatus.DRAFT,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=2),
            hold_duration=10,
        )

        normal_user = User.objects.create_user(
            email="user@test.com",
            password="TestPassword123",
            is_event_maker=False,
        )

        self.client.force_authenticate(user=normal_user)

        response = self.client.get("/api/events/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["id"],
            published_event.id,
        )

    def test_update_event_owner(self):
        event = Event.objects.create(
            organizer=self.user,
            title="Old Title",
            description="Event",
            location="Cairo",
            status=EventStatus.DRAFT,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=2),
            hold_duration=10,
        )

        response = self.client.patch(
            f"/api/events/{event.id}/update/",
            {"title": "New Title"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        event.refresh_from_db()

        self.assertEqual(
            event.title,
            "New Title",
        )

    def test_cannot_update_other_user_event(self):
        other_user = User.objects.create_user(
            email="other@test.com",
            password="TestPassword123",
            is_event_maker=True,
        )

        event = Event.objects.create(
            organizer=other_user,
            title="Other Event",
            description="Event",
            location="Cairo",
            status=EventStatus.DRAFT,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=2),
            hold_duration=10,
        )

        response = self.client.patch(
            f"/api/events/{event.id}/update/",
            {"title": "Hacked"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_publish_event(self):
        event = Event.objects.create(
            organizer=self.user,
            title="Django Conference",
            description="Event",
            location="Cairo",
            status=EventStatus.DRAFT,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=2),
            hold_duration=10,
        )

        TicketType.objects.create(
            event=event,
            name="Regular",
            price_cents=100000,
            capacity=100,
            available_inventory=100,
        )

        response = self.client.post(
            f"/api/events/{event.id}/publish/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        event.refresh_from_db()

        self.assertEqual(
            event.status,
            EventStatus.PUBLISHED,
        )

    def test_cannot_publish_event_without_ticket_type(self):
        event = Event.objects.create(
            organizer=self.user,
            title="Empty Event",
            description="Event",
            location="Cairo",
            status=EventStatus.DRAFT,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=2),
            hold_duration=10,
        )

        response = self.client.post(
            f"/api/events/{event.id}/publish/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
