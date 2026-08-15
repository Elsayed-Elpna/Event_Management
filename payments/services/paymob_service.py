from datetime import datetime
import requests
import hashlib
import hmac

from django.conf import settings


class PaymobService:

    def create_payment_intention(
        self,
        *,
        amount_cents,
        reference_id,
        items,
        billing_data,
    ):
        url = f"{settings.PAYMOB_BASE_URL}/v1/intention/"

        payload = {
            "amount": amount_cents,
            "currency": "EGP",
            "payment_methods": [
                int(settings.PAYMOB_INTEGRATION_ID),
            ],
            "items": items,
            "billing_data": billing_data,
            "special_reference": reference_id,
        }

        response = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Token {settings.PAYMOB_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        # response.raise_for_status()

        # return response.json()
        if not response.ok:
            print("PAYMOB STATUS:", response.status_code)
            print("PAYMOB RESPONSE:", response.text)

        response.raise_for_status()

        return response.json()

    def verify_transaction_hmac(
        self,
        *,
        transaction_data,
        received_hmac,
    ):
        values = [
            transaction_data["amount_cents"],
            transaction_data["created_at"],
            transaction_data["currency"],
            transaction_data["error_occured"],
            transaction_data["has_parent_transaction"],
            transaction_data["id"],
            transaction_data["integration_id"],
            transaction_data["is_3d_secure"],
            transaction_data["is_auth"],
            transaction_data["is_capture"],
            transaction_data["is_refunded"],
            transaction_data["is_standalone_payment"],
            transaction_data["is_voided"],
            transaction_data["order"]["id"],
            transaction_data["owner"],
            transaction_data["pending"],
            transaction_data["source_data"]["pan"],
            transaction_data["source_data"]["sub_type"],
            transaction_data["source_data"]["type"],
            transaction_data["success"],
        ]

        def normalize(value):
            if isinstance(value, bool):
                return str(value).lower()

            return str(value)

        concatenated_values = "".join(normalize(value) for value in values)

        calculated_hmac = hmac.new(
            settings.PAYMOB_HMAC_SECRET.encode(),
            concatenated_values.encode(),
            hashlib.sha512,
        ).hexdigest()

        return hmac.compare_digest(
            calculated_hmac,
            received_hmac,
        )

    # order

    def create_order_intention(self, *, order):
        items = [
            {
                "name": order.reservation.ticket_type.ticket_type,
                "amount": order.unit_price,
                "description": order.reservation.ticket_type.event.title,
                "quantity": order.quantity,
            }
        ]

        billing_data = {
            "apartment": "NA",
            "first_name": order.user.first_name or "User",
            "last_name": order.user.last_name or "User",
            "street": "NA",
            "building": "NA",
            "phone_number": "+201000000000",
            "city": "Cairo",
            "country": "EG",
            "email": order.user.email,
            "floor": "NA",
            "state": "Cairo",
        }

        return self.create_payment_intention(
            amount_cents=order.payment.amount,
            reference_id=f"order-{order.id}-payment-{order.payment.id}",
            items=items,
            billing_data=billing_data,
        )


    def create_refund(self, *, transaction_id, amount_cents, description):
        url = f"{settings.PAYMOB_BASE_URL}/api/acceptance/void_refund/refund"

        payload = {
            "transaction_id": str(transaction_id),
            "amount_cents": amount_cents,
        }

        response = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Token {settings.PAYMOB_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        if not response.ok:
            print("PAYMOB REFUND STATUS:", response.status_code)
            print("PAYMOB REFUND RESPONSE:", response.text)
            raise ValueError(
                f"Paymob refund failed: {response.status_code} {response.text}"
            )

        return response.json()
