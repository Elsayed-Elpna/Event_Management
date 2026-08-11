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
