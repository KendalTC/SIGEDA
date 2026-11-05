from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase


class AccountsApiTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user",
            password="12345678",
            email="user@example.com",
        )

    def test_login_returns_token_and_user(self):
        response = self.client.post(
            "/api/accounts/login/",
            {"username": "user", "password": "12345678"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["username"], "user")

    def test_login_with_invalid_credentials_returns_401(self):
        response = self.client.post(
            "/api/accounts/login/",
            {"username": "user", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_authentication(self):
        response = self.client.get("/api/accounts/me/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/accounts/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "user")

    def test_logout_deletes_token(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post("/api/accounts/logout/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Token.objects.filter(user=self.user).exists())


class PasswordManagementApiTest(APITestCase):
    def setUp(self):
        self.target_user = User.objects.create_user(
            username="operario",
            password="12345678",
        )

    def login(self, username, password):
        return self.client.post(
            "/api/accounts/login/",
            {"username": username, "password": password},
            format="json",
        )

    def test_user_changes_own_password_and_gets_a_new_token(self):
        login_response = self.login("operario", "12345678")
        old_token = login_response.data["token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old_token}")

        response = self.client.post(
            "/api/accounts/me/password/",
            {
                "current_password": "12345678",
                "new_password": "clave-nueva-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_token = response.data["token"]
        self.assertNotEqual(new_token, old_token)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old_token}")
        self.assertEqual(
            self.client.get("/api/accounts/me/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {new_token}")
        self.assertEqual(
            self.client.get("/api/accounts/me/").status_code,
            status.HTTP_200_OK,
        )

        self.client.credentials()
        self.assertEqual(
            self.login("operario", "clave-nueva-123").status_code,
            status.HTTP_200_OK,
        )

    def test_change_own_password_with_wrong_current_password(self):
        self.client.force_authenticate(self.target_user)

        response = self.client.post(
            "/api/accounts/me/password/",
            {
                "current_password": "la-que-no-es",
                "new_password": "clave-nueva-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)

        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.check_password("12345678"))

    def test_change_own_password_rejects_short_password(self):
        self.client.force_authenticate(self.target_user)

        response = self.client.post(
            "/api/accounts/me/password/",
            {
                "current_password": "12345678",
                "new_password": "corta",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.check_password("12345678"))

    def test_change_own_password_requires_authentication(self):
        response = self.client.post(
            "/api/accounts/me/password/",
            {
                "current_password": "12345678",
                "new_password": "clave-nueva-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
