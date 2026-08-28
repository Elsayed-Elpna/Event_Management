import requests

from django.conf import settings
from django.db import transaction

from payments.models import Payment
from payments.services.paymob_service import PaymobService
from subscriptions.models import Subscription, SubscriptionStatus


def create_subscription(*, user):
    price_cents = settings.SUBSCRIPTION_PRICE_CENTS

    # ---------------------------------
    # 1. Create pending rows (short tx, no locks on shared rows)
    # ---------------------------------
    subscription, payment = _create_pending_subscription(
        user=user,
        price_cents=price_cents,
    )

    # ---------------------------------
    # 2. Call Paymob with NO transaction or locks held
    # ---------------------------------
    try:
        paymob_response = _request_payment_intention(
            user=user,
            subscription=subscription,
            payment=payment,
            price_cents=price_cents,
        )
    except requests.RequestException as exc:
        raise ValueError(
            "Could not contact the payment provider. Please try again."
        ) from exc

    # ---------------------------------
    # 3. Persist provider reference (short tx)
    # ---------------------------------
    effective_reference = _save_provider_reference(
        payment=payment,
        provider_reference=paymob_response["id"],
    )

    if effective_reference != paymob_response["id"]:
        paymob_response["id"] = effective_reference

    payment.provider_reference = effective_reference

    return subscription, paymob_response


@transaction.atomic
def _create_pending_subscription(*, user, price_cents):
    existing = getattr(user, "subscription", None)

    # A user only ever owns one subscription row (OneToOne with the user).
    # If a previous attempt/subscription exists but is no longer active
    # (PENDING from a failed checkout, EXPIRED, or CANCELLED), reuse it so
    # the user can retry or renew instead of being locked out forever.
    if existing is not None:
        subscription = existing
        subscription.status = SubscriptionStatus.PENDING
        subscription.starts_at = None
        subscription.expires_at = None
        subscription.amount_cents = price_cents

        payment = Payment.objects.create(
            payment_type=Payment.PaymentType.SUBSCRIPTION,
            amount=price_cents,
            status=Payment.PaymentStatus.PENDING,
        )

        subscription.payment = payment

        subscription.save(
            update_fields=[
                "status",
                "starts_at",
                "expires_at",
                "amount_cents",
                "payment",
                "updated_at",
            ]
        )

        return subscription, payment

    subscription = Subscription.objects.create(
        user=user,
        amount_cents=price_cents,
        status=SubscriptionStatus.PENDING,
    )

    payment = Payment.objects.create(
        payment_type=Payment.PaymentType.SUBSCRIPTION,
        amount=price_cents,
        status=Payment.PaymentStatus.PENDING,
    )

    subscription.payment = payment
    subscription.save(update_fields=["payment", "updated_at"])

    return subscription, payment


def _request_payment_intention(*, user, subscription, payment, price_cents):
    paymob_service = PaymobService()

    billing_data = {
        "apartment": "NA",
        "first_name": user.first_name or "Customer",
        "last_name": user.last_name or "User",
        "street": "NA",
        "building": "NA",
        "phone_number": "+201000000000",
        "city": "Cairo",
        "country": "EG",
        "email": user.email,
        "floor": "NA",
        "state": "Cairo",
    }

    items = [
        {
            "name": "Event Maker Subscription",
            "amount": price_cents,
            "description": "Event Maker Subscription",
            "quantity": 1,
        }
    ]

    return paymob_service.create_payment_intention(
        amount_cents=price_cents,
        reference_id=f"subscription-{subscription.id}-payment-{payment.id}",
        items=items,
        billing_data=billing_data,
    )


@transaction.atomic
def _save_provider_reference(*, payment, provider_reference):
    payment = Payment.objects.select_for_update().get(id=payment.id)

    if payment.provider_reference:
        return payment.provider_reference

    payment.provider_reference = provider_reference

    payment.save(
        update_fields=[
            "provider_reference",
            "updated_at",
        ]
    )

    return payment.provider_reference
