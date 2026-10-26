from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from credential_app.models import Credential
from credential_app.views import (
    CredentialDetailView,
    CredentialListView,
)
from vault_app.models import Category, Vault


User = get_user_model()


class CredentialIntegrationTests(TestCase):
    """
    Integration tests for Credential URLs and HTTP workflows.

    User, Vault, and Category are created as database prerequisites.
    Credential operations are performed through Django's test Client.

    These tests verify routing, authentication, forms, services,
    authorization, and database effects without inspecting HTML.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="amir",
            password="Test-Password-123!",
        )

        self.vault = Vault.objects.create(
            user=self.user,
            name="Personal",
            slug="personal",
            is_default=True,
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Social",
        )

        self.client.force_login(self.user)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def vault_url_kwargs(self, user=None, vault=None):
        user = user or self.user
        vault = vault or self.vault

        return {
            "username": user.username,
            "vault_slug": vault.slug,
        }

    def create_url(self, user=None, vault=None):
        return reverse(
            "credential_app:create",
            kwargs=self.vault_url_kwargs(user=user, vault=vault),
        )

    def list_url(self, user=None, vault=None):
        return reverse(
            "credential_app:list",
            kwargs=self.vault_url_kwargs(user=user, vault=vault),
        )

    def detail_url(self, credential, user=None, vault=None):
        kwargs = self.vault_url_kwargs(user=user, vault=vault)
        kwargs["pk"] = credential.pk

        return reverse(
            "credential_app:detail",
            kwargs=kwargs,
        )

    def create_payload(self, **overrides):
        payload = {
            "service_name": "GitHub",
            "service_url": "https://github.com/",
            "login_username": "amir",
            "login_email": "amir@example.com",
            "password": "Vault-Password-2026!",
            "confirm_password": "Vault-Password-2026!",
            "category": str(self.category.pk),
            "notes": "Primary account",
            "is_favorite": "on",
        }
        payload.update(overrides)
        return payload

    def create_existing_credential(self, **overrides):
        data = {
            "vault": self.vault,
            "category": self.category,
            "service_name": "GitHub",
            "service_url": "https://github.com/",
            "login_username": "amir",
            "login_email": "amir@example.com",
            "password_ciphertext": "existing-ciphertext",
            "notes": "",
            "is_favorite": False,
        }
        data.update(overrides)

        return Credential.objects.create(**data)

    # ------------------------------------------------------------------
    # URL configuration
    # ------------------------------------------------------------------

    def test_all_named_routes_resolve(self):
        base_kwargs = self.vault_url_kwargs()

        route_cases = [
            ("list", base_kwargs),
            ("create", base_kwargs),
            ("detail", {**base_kwargs, "pk": 1}),
            ("update", {**base_kwargs, "pk": 1}),
            ("delete", {**base_kwargs, "pk": 1}),
            ("rotate_password", {**base_kwargs, "pk": 1}),
            ("toggle_favorite", {**base_kwargs, "pk": 1}),
            ("move_to_vault", {**base_kwargs, "pk": 1}),
        ]

        for route_name, kwargs in route_cases:
            with self.subTest(route_name=route_name):
                url = reverse(
                    f"credential_app:{route_name}",
                    kwargs=kwargs,
                )

                self.assertTrue(url.startswith("/vault/"))

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def test_anonymous_user_cannot_access_credential_list(self):
        self.client.logout()

        response = self.client.get(self.list_url())

        self.assertEqual(response.status_code, 302)

    # ------------------------------------------------------------------
    # Create Credential
    # ------------------------------------------------------------------

    def test_authenticated_user_can_create_credential_through_client(self):
        password = "Vault-Password-2026!"

        with patch(
            "credential_app.services.credential_service."
            "EncryptionService.encrypt",
            return_value="encrypted-test-password",
        ) as encrypt_mock:
            response = self.client.post(
                self.create_url(),
                self.create_payload(
                    password=password,
                    confirm_password=password,
                ),
            )

        self.assertEqual(response.status_code, 302)

        credential = Credential.objects.get(
            vault=self.vault,
            service_name="GitHub",
        )

        self.assertEqual(credential.category, self.category)
        self.assertEqual(credential.login_username, "amir")
        self.assertEqual(
            credential.password_ciphertext,
            "encrypted-test-password",
        )
        self.assertTrue(credential.is_favorite)

        # The raw password must not be stored as the ciphertext.
        self.assertNotEqual(
            credential.password_ciphertext,
            password,
        )

        encrypt_mock.assert_called_once()

        expected_redirect = reverse(
            "credential_app:detail",
            kwargs={
                **self.vault_url_kwargs(),
                "pk": credential.pk,
            },
        )
        self.assertEqual(response["Location"], expected_redirect)

    def test_user_cannot_create_credential_in_another_users_vault(self):
        another_user = User.objects.create_user(
            username="another_user",
            password="Another-Test-Password-123!",
        )

        another_vault = Vault.objects.create(
            user=another_user,
            name="Personal",
            slug="personal",
        )

        response = self.client.post(
            self.create_url(
                user=another_user,
                vault=another_vault,
            ),
            self.create_payload(),
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Credential.objects.count(), 0)

    def test_create_rejects_category_owned_by_another_user(self):
        another_user = User.objects.create_user(
            username="category_owner",
            password="Another-Test-Password-123!",
        )

        another_category = Category.objects.create(
            user=another_user,
            name="Private",
        )

        # No real template is needed to test the invalid form response.
        with patch(
            "credential_app.views.render",
            return_value=HttpResponse(status=200),
        ):
            response = self.client.post(
                self.create_url(),
                self.create_payload(
                    category=str(another_category.pk),
                ),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Credential.objects.count(), 0)

    def test_duplicate_service_name_does_not_create_second_credential(self):
        password = "Vault-Password-2026!"

        with patch(
            "credential_app.services.credential_service."
            "EncryptionService.encrypt",
            return_value="encrypted-test-password",
        ):
            first_response = self.client.post(
                self.create_url(),
                self.create_payload(),
            )

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(
            Credential.objects.filter(
                vault=self.vault,
                service_name="GitHub",
            ).count(),
            1,
        )

        # DuplicateCredential is handled by the view and returns a form
        # response. Stub rendering so the test does not depend on HTML.
        with patch(
            "credential_app.views.render",
            return_value=HttpResponse(status=200),
        ):
            duplicate_response = self.client.post(
                self.create_url(),
                self.create_payload(
                    password=password,
                    confirm_password=password,
                ),
            )

        self.assertEqual(duplicate_response.status_code, 200)

        self.assertEqual(
            Credential.objects.filter(
                vault=self.vault,
                service_name="GitHub",
            ).count(),
            1,
        )

    # ------------------------------------------------------------------
    # List and Detail HTTP routes
    # ------------------------------------------------------------------

    def test_list_route_works_without_rendering_a_real_template(self):
        with (
            patch(
                "credential_app.views.render",
                return_value=HttpResponse(status=200),
            ),
            patch.object(
                CredentialListView,
                "render_to_response",
                return_value=HttpResponse(status=200),
            ),
        ):
            response = self.client.get(self.list_url())

        self.assertEqual(response.status_code, 200)

    def test_detail_route_works_without_rendering_a_real_template(self):
        credential = self.create_existing_credential()

        with (
            patch(
                "credential_app.views.render",
                return_value=HttpResponse(status=200),
            ),
            patch.object(
                CredentialDetailView,
                "render_to_response",
                return_value=HttpResponse(status=200),
            ),
            patch(
                "credential_app.views.EncryptionService.decrypt",
                return_value="decrypted-test-password",
            ) as decrypt_mock,
        ):
            response = self.client.get(
                self.detail_url(credential),
            )

        self.assertEqual(response.status_code, 200)

        decrypt_mock.assert_called_once_with(
            credential.password_ciphertext,
        )

