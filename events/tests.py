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
            ticket_type="REGULAR",
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


#################################################
###ticket test case


class TicketTypeAPITestCase(APITestCase):

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
        )

        self.event = Event.objects.create(
            organizer=self.user,
            title="Django Conference",
            description="Backend event",
            location="Cairo",
            status=EventStatus.DRAFT,
            starts_at="2026-09-01T18:00:00Z",
            ends_at="2026-09-01T22:00:00Z",
            hold_duration=10,
        )

        self.client.force_authenticate(user=self.user)

        self.ticket_data = {
            "ticket_type": "REGULAR",
            "price_cents": 100000,
            "capacity": 100,
        }

    def test_create_regular_ticket(self):
        response = self.client.post(
            f"/api/events/{self.event.id}/ticket-types/",
            self.ticket_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        ticket = TicketType.objects.get()

        self.assertEqual(
            ticket.ticket_type,
            TicketType.TicketTypeChoice.REGULAR,
        )

        self.assertEqual(
            ticket.capacity,
            100,
        )

        self.assertEqual(
            ticket.available_inventory,
            100,
        )

    def test_create_vip_ticket(self):
        response = self.client.post(
            f"/api/events/{self.event.id}/ticket-types/",
            {
                "ticket_type": "VIP",
                "price_cents": 200000,
                "capacity": 20,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        ticket = TicketType.objects.get()

        self.assertEqual(
            ticket.ticket_type,
            TicketType.TicketTypeChoice.VIP,
        )

    def test_cannot_create_duplicate_ticket_type(self):
        TicketType.objects.create(
            event=self.event,
            ticket_type=TicketType.TicketTypeChoice.REGULAR,
            price_cents=100000,
            capacity=100,
            available_inventory=100,
        )

        response = self.client.post(
            f"/api/events/{self.event.id}/ticket-types/",
            self.ticket_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_invalid_ticket_type(self):
        response = self.client.post(
            f"/api/events/{self.event.id}/ticket-types/",
            {
                "ticket_type": "PREMIUM",
                "price_cents": 100000,
                "capacity": 100,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_invalid_price(self):
        response = self.client.post(
            f"/api/events/{self.event.id}/ticket-types/",
            {
                "ticket_type": "REGULAR",
                "price_cents": 0,
                "capacity": 100,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_invalid_capacity(self):
        response = self.client.post(
            f"/api/events/{self.event.id}/ticket-types/",
            {
                "ticket_type": "REGULAR",
                "price_cents": 100000,
                "capacity": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_normal_user_cannot_create_ticket(self):
        user = User.objects.create_user(
            email="user@test.com",
            password="TestPassword123",
            is_event_maker=False,
        )

        self.client.force_authenticate(user=user)

        response = self.client.post(
            f"/api/events/{self.event.id}/ticket-types/",
            self.ticket_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_other_event_maker_cannot_create_ticket(self):
        other_user = User.objects.create_user(
            email="other@test.com",
            password="TestPassword123",
            is_event_maker=True,
        )

        self.client.force_authenticate(user=other_user)

        response = self.client.post(
            f"/api/events/{self.event.id}/ticket-types/",
            self.ticket_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cannot_create_ticket_for_published_event(self):
        self.event.status = Event.EventStatus.PUBLISHED
        self.event.save(update_fields=["status"])

        response = self.client.post(
            f"/api/events/{self.event.id}/ticket-types/",
            self.ticket_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_update_capacity(self):
        ticket = TicketType.objects.create(
            event=self.event,
            ticket_type=TicketType.TicketTypeChoice.REGULAR,
            price_cents=100000,
            capacity=100,
            available_inventory=100,
        )

        response = self.client.patch(
            f"/api/ticket-types/{ticket.id}/",
            {
                "capacity": 150,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        ticket.refresh_from_db()

        self.assertEqual(
            ticket.capacity,
            150,
        )

        self.assertEqual(
            ticket.available_inventory,
            150,
        )

    def test_cannot_update_published_ticket(self):
        ticket = TicketType.objects.create(
            event=self.event,
            ticket_type=TicketType.TicketTypeChoice.REGULAR,
            price_cents=100000,
            capacity=100,
            available_inventory=100,
        )

        self.event.status = Event.EventStatus.PUBLISHED
        self.event.save(update_fields=["status"])

        response = self.client.patch(
            f"/api/ticket-types/{ticket.id}/",
            {
                "price_cents": 150000,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


#################################################
###event maker permission test case


class EventMakerPermissionTestCase(APITestCase):

    def setUp(self):
        self.maker = User.objects.create_user(
            email="perm_maker@test.com",
            password="TestPassword123",
            is_event_maker=True,
        )

        self.normal_user = User.objects.create_user(
            email="perm_normal@test.com",
            password="TestPassword123",
            is_event_maker=False,
        )

        self.event = Event.objects.create(
            organizer=self.maker,
            title="Permission Event",
            description="Event",
            location="Cairo",
            status=EventStatus.DRAFT,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=2),
            hold_duration=10,
        )

        self.ticket = TicketType.objects.create(
            event=self.event,
            ticket_type=TicketType.TicketTypeChoice.REGULAR,
            price_cents=100000,
            capacity=100,
            available_inventory=100,
        )

        self.event_data = {
            "title": "Django Conference",
            "description": "Backend event",
            "location": "Cairo",
            "starts_at": "2026-09-01T18:00:00Z",
            "ends_at": "2026-09-01T22:00:00Z",
            "hold_duration": 10,
        }

        self.ticket_data = {
            "ticket_type": "REGULAR",
            "price_cents": 100000,
            "capacity": 100,
        }

    #############################
    ###anonymous users -> 401###

    def test_anonymous_cannot_create_event(self):
        response = self.client.post(
            "/api/events/",
            self.event_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_anonymous_cannot_update_event(self):
        response = self.client.patch(
            f"/api/events/{self.event.id}/update/",
            {"title": "Hacked"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_anonymous_cannot_publish_event(self):
        response = self.client.post(
            f"/api/events/{self.event.id}/publish/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_anonymous_cannot_create_ticket_type(self):
        response = self.client.post(
            f"/api/events/{self.event.id}/ticket-types/",
            self.ticket_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_anonymous_cannot_update_ticket_type(self):
        response = self.client.patch(
            f"/api/ticket-types/{self.ticket.id}/",
            {"price_cents": 150000},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_anonymous_cannot_list_events(self):
        response = self.client.get("/api/events/")

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    ############################################
    ###authenticated non makers -> 403###

    def test_non_maker_cannot_create_event(self):
        self.client.force_authenticate(user=self.normal_user)

        response = self.client.post(
            "/api/events/",
            self.event_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_maker_cannot_update_event(self):
        self.client.force_authenticate(user=self.normal_user)

        response = self.client.patch(
            f"/api/events/{self.event.id}/update/",
            {"title": "Hacked"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_maker_cannot_publish_event(self):
        self.client.force_authenticate(user=self.normal_user)

        response = self.client.post(
            f"/api/events/{self.event.id}/publish/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_maker_cannot_create_ticket_type(self):
        self.client.force_authenticate(user=self.normal_user)

        response = self.client.post(
            f"/api/events/{self.event.id}/ticket-types/",
            self.ticket_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_maker_cannot_update_ticket_type(self):
        self.client.force_authenticate(user=self.normal_user)

        response = self.client.patch(
            f"/api/ticket-types/{self.ticket.id}/",
            {"price_cents": 150000},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    ##########################################################
    ###non makers keep read access (per-method permission)###

    def test_non_maker_can_list_published_events(self):
        self.event.status = EventStatus.PUBLISHED
        self.event.save(update_fields=["status"])

        self.client.force_authenticate(user=self.normal_user)

        response = self.client.get("/api/events/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
