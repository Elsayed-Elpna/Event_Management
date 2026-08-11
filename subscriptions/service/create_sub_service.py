from django.conf import settings
from django.db import transaction

from payments.models import Payment
from payments.services.paymob_service import PaymobService
from subscriptions.models import Subscription, SubscriptionStatus


@transaction.atomic
def create_subscription(*, user):
    price_cents = settings.SUBSCRIPTION_PRICE_CENTS

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

    paymob_response = paymob_service.create_payment_intention(
        amount_cents=price_cents,
        reference_id=f"subscription-{subscription.id}",
        items=items,
        billing_data=billing_data,
    )

    payment.provider_reference = paymob_response["id"]

    payment.save(
        update_fields=[
            "provider_reference",
            "updated_at",
        ]
    )

    return subscription, paymob_response
