from django.db import transaction

from django.utils.dateparse import parse_datetime
from django.utils import timezone
from datetime import timedelta

from subscriptions.models import Subscription, SubscriptionStatus
from payments.models import Payment
from audit.models import AuditLog


@transaction.atomic
def process_successful_payment(*, transaction_data):
    merchant_order_id = transaction_data["order"]["merchant_order_id"]

    if not merchant_order_id.startswith("subscription-"):
        raise ValueError("Unsupported merchant order")

    parts = merchant_order_id.split("-")

    if len(parts) != 4:
        raise ValueError("Invalid subscription merchant order")

    subscription_id = parts[1]
    payment_id = parts[3]

    subscription = (
        Subscription.objects.select_for_update(of=("self",))
        .select_related("payment")
        .get(id=subscription_id)
    )

    payment = subscription.payment

    if payment.id != int(payment_id):
        raise ValueError("Payment does not belong to subscription")

    if payment.amount != transaction_data["amount_cents"]:
        raise ValueError("Payment amount mismatch")

    transaction_id = str(transaction_data["id"])

    # idempotency

    if payment.status == Payment.PaymentStatus.SUCCESS:
        return subscription

    payment.provider_transaction_id = transaction_id
    payment.status = Payment.PaymentStatus.SUCCESS

    paid_at = parse_datetime(transaction_data["created_at"])

    if timezone.is_naive(paid_at):
        paid_at = timezone.make_aware(paid_at)

    payment.paid_at = paid_at

    payment.save(
        update_fields=[
            "provider_transaction_id",
            "status",
            "paid_at",
            "updated_at",
        ]
    )

    # addlogs

    AuditLog.objects.create(
        actor=subscription.user,
        action=AuditLog.AuditAction.PAYMENT_SUCCESS,
        entity_type="Payment",
        entity_id=payment.id,
        reason="Subscription payment confirmed by Paymob",
        metadata={
            "provider_transaction_id": transaction_id,
            "amount_cents": payment.amount,
        },
    )

    user = subscription.user
    user.is_event_maker = True
    user.save(update_fields=["is_event_maker", "updated_at"])
    subscription.status = SubscriptionStatus.ACTIVE

    starts_at = parse_datetime(transaction_data["created_at"])

    # Paymob sends a naive ISO timestamp; make it aware before using it so
    # expires_at is computed against the same instant in UTC.
    if timezone.is_naive(starts_at):
        starts_at = timezone.make_aware(starts_at)

    subscription.starts_at = starts_at
    subscription.expires_at = starts_at + timedelta(days=30)

    subscription.save(
        update_fields=[
            "status",
            "starts_at",
            "expires_at",
            "updated_at",
        ]
    )
    AuditLog.objects.create(
        actor=subscription.user,
        action=AuditLog.AuditAction.SUBSCRIPTION_ACTIVATED,
        entity_type="Subscription",
        entity_id=subscription.id,
        reason="Subscription activated after successful Paymob payment",
        metadata={
            "payment_id": payment.id,
            "expires_at": subscription.expires_at.isoformat(),
        },
    )

    return subscription
