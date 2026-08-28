from datetime import timedelta

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User


class JWTConfigTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="jwt@test.com",
            password="TestPassword123",
        )

    def _get_tokens(self):
        response = self.client.post(
            "/api/token/",
            {"email": "jwt@test.com", "password": "TestPassword123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["access"], response.data["refresh"]

    def test_access_token_lifetime_is_one_hour(self):
        access, _ = self._get_tokens()

        token = AccessToken(access)
        lifetime = timedelta(seconds=token["exp"] - token["iat"])

        self.assertEqual(lifetime, timedelta(hours=1))

    def test_access_token_authenticates_profile_view(self):
        access, _ = self._get_tokens()

        response = self.client.get(
            "/api/profile/",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)