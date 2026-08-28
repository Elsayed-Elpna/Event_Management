from unittest.mock import patch

import requests

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from payments.models import Payment
from subscriptions.models import Subscription, SubscriptionStatus
from subscriptions.service.create_sub_service import (
    _create_pending_subscription,
    _save_provider_reference,
)


class SubscriptionCreateAPITestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="sub@test.com",
            password="TestPassword123",
            is_event_maker=False,
        )

        self.client.force_authenticate(user=self.user)

    def test_create_subscription_success(self):
        with patch(
            "payments.services.paymob_service.PaymobService.create_payment_intention",
            return_value={"id": "ref-1", "client_secret": "secret-1"},
        ):
            response = self.client.post("/api/subscriptions/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("secret-1", response.data["checkout_url"])
        self.assertEqual(
            response.data["payment"]["provider_reference"],
            "ref-1",
        )

        subscription = Subscription.objects.get(user=self.user)

        self.assertEqual(
            subscription.status,
            SubscriptionStatus.PENDING,
        )
        self.assertIsNotNone(subscription.payment_id)
        self.assertEqual(
            subscription.payment.provider_reference,
            "ref-1",
        )
        self.assertEqual(
            subscription.payment.status,
            Payment.PaymentStatus.PENDING,
        )

    def test_provider_outage_returns_400_and_keeps_payment_retryable(self):
        with patch(
            "payments.services.paymob_service.PaymobService.create_payment_intention",
            side_effect=requests.ConnectionError("boom"),
        ):
            response = self.client.post("/api/subscriptions/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Could not contact the payment provider",
            response.data["detail"],
        )

        subscription = Subscription.objects.get(user=self.user)

        self.assertEqual(
            subscription.status,
            SubscriptionStatus.PENDING,
        )
        self.assertIsNone(subscription.payment.provider_reference)

    def test_retry_after_provider_outage_succeeds(self):
        with patch(
            "payments.services.paymob_service.PaymobService.create_payment_intention",
            side_effect=requests.ConnectionError("boom"),
        ):
            first_response = self.client.post(
                "/api/subscriptions/", {}, format="json"
            )

        self.assertEqual(first_response.status_code, status.HTTP_400_BAD_REQUEST)

        subscription_before = Subscription.objects.get(user=self.user)

        self.assertEqual(subscription_before.status, SubscriptionStatus.PENDING)

        with patch(
            "payments.services.paymob_service.PaymobService.create_payment_intention",
            return_value={"id": "ref-retry", "client_secret": "secret-retry"},
        ):
            second_response = self.client.post(
                "/api/subscriptions/", {}, format="json"
            )

        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertIn("secret-retry", second_response.data["checkout_url"])
        self.assertEqual(
            second_response.data["payment"]["provider_reference"],
            "ref-retry",
        )

        subscription = Subscription.objects.get(user=self.user)

        self.assertEqual(subscription.id, subscription_before.id)
        self.assertEqual(subscription.status, SubscriptionStatus.PENDING)
        self.assertNotEqual(subscription.payment_id, subscription_before.payment_id)
        self.assertEqual(subscription.payment.provider_reference, "ref-retry")
        self.assertEqual(subscription.amount_cents, 100000)
        self.assertEqual(Payment.objects.count(), 2)

    def test_renew_after_expired_succeeds(self):
        expired = Subscription.objects.create(
            user=self.user,
            amount_cents=100000,
            status=SubscriptionStatus.EXPIRED,
        )

        with patch(
            "payments.services.paymob_service.PaymobService.create_payment_intention",
            return_value={"id": "ref-renew", "client_secret": "secret-renew"},
        ):
            response = self.client.post("/api/subscriptions/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        subscription = Subscription.objects.get(user=self.user)

        self.assertEqual(subscription.id, expired.id)
        self.assertEqual(subscription.status, SubscriptionStatus.PENDING)
        self.assertIsNone(subscription.starts_at)
        self.assertIsNone(subscription.expires_at)
        self.assertEqual(subscription.amount_cents, 100000)

    def test_cannot_buy_while_active(self):
        Subscription.objects.create(
            user=self.user,
            amount_cents=100000,
            status=SubscriptionStatus.ACTIVE,
        )

        response = self.client.post("/api/subscriptions/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "active subscription",
            str(response.data["non_field_errors"]),
        )
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)

    def test_provider_reference_first_writer_wins(self):
        _, payment = _create_pending_subscription(
            user=self.user,
            price_cents=100000,
        )

        payment.provider_reference = "winner"
        payment.save(update_fields=["provider_reference"])

        result = _save_provider_reference(
            payment=payment,
            provider_reference="loser",
        )

        self.assertEqual(result, "winner")

        payment.refresh_from_db()

        self.assertEqual(payment.provider_reference, "winner")
