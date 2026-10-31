import json

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.test import RequestFactory, TestCase

from common.security.encryption.exceptions import EncryptionError
from credential_app.models import Credential, CredentialHistory
from credential_app.views import (
    CredentialCreateView,
    CredentialDeleteView,
    CredentialDetailView,
    CredentialListView,
    CredentialMoveToVaultView,
    CredentialRotatePasswordView,
    CredentialRevealPasswordView,
    CredentialToggleFavoriteView,
    CredentialUpdateView,
)
from vault_app.models import Category, Vault


User = get_user_model()


class CredentialViewTests(TestCase):
    PASSWORD = "Strong-Test-Password-123!"

    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(
            username="alice",
            password="test-password",
        )
        cls.bob = User.objects.create_user(
            username="bob",
            password="test-password",
        )

        cls.alice_vault = Vault.objects.create(
            user=cls.alice,
            name="Personal",
            slug="personal",
            description="",
        )
        cls.alice_work_vault = Vault.objects.create(
            user=cls.alice,
            name="Work",
            slug="work",
            description="",
        )
        cls.bob_vault = Vault.objects.create(
            user=cls.bob,
            name="Personal",
            slug="personal",
            description="",
        )

        cls.alice_category = Category.objects.create(
            user=cls.alice,
            name="Social",
        )
        cls.bob_category = Category.objects.create(
            user=cls.bob,
            name="Social",
        )

        cls.alice_credential = Credential.objects.create(
            vault=cls.alice_vault,
            category=cls.alice_category,
            service_name="GitHub",
            service_url="https://github.com",
            login_username="alice-dev",
            login_email="alice@example.com",
            password_ciphertext="encrypted-alice-password",
            notes="Personal development",
        )
        cls.alice_work_credential = Credential.objects.create(
            vault=cls.alice_work_vault,
            category=None,
            service_name="GitLab",
            service_url="https://gitlab.com",
            login_username="alice-work",
            login_email="work@example.com",
            password_ciphertext="encrypted-work-password",
        )
        cls.bob_credential = Credential.objects.create(
            vault=cls.bob_vault,
            category=cls.bob_category,
            service_name="GitHub",
            service_url="https://github.com",
            login_username="bob-dev",
            login_email="bob@example.com",
            password_ciphertext="encrypted-bob-password",
        )

    def setUp(self):
        self.factory = RequestFactory()

    def dispatch_view(
        self,
        view_class,
        *,
        method="get",
        data=None,
        user=None,
        path=None,
        **url_kwargs,
    ):
        """
        Call a class-based view without depending on production URLs.
        """
        path = path or "/alice/personal/credentials/"

        if method.lower() == "post":
            request = self.factory.post(path, data=data or {})
        else:
            request = getattr(self.factory, method.lower())(path)

        request.user = self.alice if user is None else user

        kwargs = {
            "username": "alice",
            "vault_slug": "personal",
        }
        kwargs.update(url_kwargs)

        return view_class.as_view()(request, **kwargs)

    def create_form_data(self, **overrides):
        data = {
            "service_name": "New Service",
            "service_url": "https://example.com",
            "login_username": "alice-new",
            "login_email": "new@example.com",
            "category": str(self.alice_category.pk),
            "notes": "Test notes",
            "password": self.PASSWORD,
            "confirm_password": self.PASSWORD,
        }
        data.update(overrides)
        return data

    def update_form_data(self, **overrides):
        data = {
            "service_name": "GitHub Updated",
            "service_url": "https://github.com",
            "login_username": "alice-updated",
            "login_email": "updated@example.com",
            "category": str(self.alice_category.pk),
            "notes": "Updated notes",
            "is_favorite": "on",
        }
        data.update(overrides)
        return data

    # ---------------------------------------------------------
    # Authentication and ownership
    # ---------------------------------------------------------

    def test_unauthenticated_user_is_redirected(self):
        with patch(
            "django.contrib.auth.mixins.redirect_to_login",
            return_value=HttpResponseRedirect("/login/"),
        ):
            response = self.dispatch_view(
                CredentialListView,
                user=AnonymousUser(),
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/login/")

    def test_wrong_username_in_url_returns_404(self):
        with self.assertRaises(Http404):
            self.dispatch_view(
                CredentialDetailView,
                username="bob",
                pk=self.bob_credential.pk,
            )

    def test_credential_from_another_users_vault_returns_404(self):
        with self.assertRaises(Http404):
            self.dispatch_view(
                CredentialDetailView,
                pk=self.bob_credential.pk,
            )

    def test_credential_from_another_vault_returns_404(self):
        with self.assertRaises(Http404):
            self.dispatch_view(
                CredentialDetailView,
                pk=self.alice_work_credential.pk,
            )

    def test_foreign_credential_is_rejected_by_mutating_views(self):
        cases = [
            (CredentialUpdateView, "get"),
            (CredentialDeleteView, "get"),
            (CredentialRotatePasswordView, "get"),
            (CredentialRevealPasswordView, "post"),
            (CredentialMoveToVaultView, "get"),
            (CredentialToggleFavoriteView, "post"),
        ]

        for view_class, method in cases:
            with self.subTest(view=view_class.__name__):
                with self.assertRaises(Http404):
                    self.dispatch_view(
                        view_class,
                        method=method,
                        pk=self.bob_credential.pk,
                    )

        self.bob_credential.refresh_from_db()
        self.assertEqual(
            self.bob_credential.password_ciphertext,
            "encrypted-bob-password",
        )

    # ---------------------------------------------------------
    # List
    # ---------------------------------------------------------

    def test_list_contains_only_credentials_from_selected_vault(self):
        response = self.dispatch_view(CredentialListView)

        credential_ids = set(
            response.context_data["credentials"].values_list(
                "pk",
                flat=True,
            )
        )

        self.assertSetEqual(
            credential_ids,
            {self.alice_credential.pk},
        )

    def test_list_search_is_limited_to_selected_vault(self):
        response = self.dispatch_view(
            CredentialListView,
            path="/alice/personal/credentials/?q=GitLab",
        )

        self.assertFalse(
            response.context_data["credentials"].exists()
        )

    def test_list_can_filter_favorites(self):
        self.alice_credential.is_favorite = True
        self.alice_credential.save(update_fields=["is_favorite"])

        response = self.dispatch_view(
            CredentialListView,
            path="/alice/personal/credentials/?favorites=1",
        )

        credentials = response.context_data["credentials"]

        self.assertSetEqual(
            set(credentials.values_list("pk", flat=True)),
            {self.alice_credential.pk},
        )

    # ---------------------------------------------------------
    # Detail
    # ---------------------------------------------------------

    def test_detail_does_not_decrypt_or_embed_password_in_initial_response(self):
        with patch(
            "credential_app.views.EncryptionService.decrypt",
        ) as decrypt:
            response = self.dispatch_view(
                CredentialDetailView,
                pk=self.alice_credential.pk,
            )

        decrypt.assert_not_called()
        self.assertEqual(
            response.context_data["credential"],
            self.alice_credential,
        )
        self.assertIn("password_reveal_url", response.context_data)
        self.assertNotIn("decrypted_password", response.context_data)
        self.assertNotIn("password_unavailable", response.context_data)

    def test_password_is_returned_only_by_explicit_reveal_post(self):
        with patch(
            "credential_app.views.EncryptionService.decrypt",
            return_value="plain-test-password",
        ) as decrypt:
            response = self.dispatch_view(
                CredentialRevealPasswordView,
                method="post",
                pk=self.alice_credential.pk,
            )

        decrypt.assert_called_once_with(self.alice_credential.password_ciphertext)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content),
            {"password": "plain-test-password"},
        )
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))

    def test_password_reveal_handles_decryption_error(self):
        with patch(
            "credential_app.views.EncryptionService.decrypt",
            side_effect=EncryptionError("decryption failed"),
        ):
            response = self.dispatch_view(
                CredentialRevealPasswordView,
                method="post",
                pk=self.alice_credential.pk,
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("error", json.loads(response.content))

    def test_password_reveal_get_is_not_allowed(self):
        response = self.dispatch_view(
            CredentialRevealPasswordView,
            method="get",
            pk=self.alice_credential.pk,
        )
        self.assertEqual(response.status_code, 405)

    def test_rendered_detail_page_never_contains_stored_ciphertext(self):
        self.client.force_login(self.alice)
        url = f"/vault/{self.alice.username}/{self.alice_vault.slug}/credentials/{self.alice_credential.pk}/"

        with patch("credential_app.views.EncryptionService.decrypt") as decrypt:
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        decrypt.assert_not_called()
        self.assertContains(response, "Load password")
        self.assertNotContains(response, self.alice_credential.password_ciphertext)

    def test_detail_response_is_marked_not_cacheable(self):
        response = self.dispatch_view(
            CredentialDetailView,
            pk=self.alice_credential.pk,
        )

        self.assertIn(
            "no-store",
            response.headers.get("Cache-Control", ""),
        )

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    def test_create_get_displays_form_for_selected_vault(self):
        with patch(
            "credential_app.views.render",
            return_value=HttpResponse("rendered"),
        ) as mock_render:
            response = self.dispatch_view(
                CredentialCreateView,
            )

        self.assertEqual(response.status_code, 200)

        context = mock_render.call_args.args[2]

        self.assertEqual(context["vault"], self.alice_vault)
        self.assertIn("form", context)

    def test_create_post_saves_credential_with_encrypted_password(self):
        with (
            patch(
                "credential_app.services.credential_service."
                "EncryptionService.encrypt",
                return_value="new-encrypted-password",
            ) as encrypt,
            patch(
                "credential_app.views.redirect",
                return_value=HttpResponseRedirect("/redirect/"),
            ) as redirect,
        ):
            response = self.dispatch_view(
                CredentialCreateView,
                method="post",
                data=self.create_form_data(),
            )

        self.assertEqual(response.status_code, 302)

        credential = Credential.objects.get(
            vault=self.alice_vault,
            service_name="New Service",
        )

        self.assertEqual(
            credential.password_ciphertext,
            "new-encrypted-password",
        )
        encrypt.assert_called_once_with(self.PASSWORD)

        redirect.assert_called_once_with(
            "credential_app:detail",
            username="alice",
            vault_slug="personal",
            pk=credential.pk,
        )

    def test_create_rejects_mismatched_password_confirmation(self):
        data = self.create_form_data(
            password=self.PASSWORD,
            confirm_password="Different-Strong-Password-123!",
        )

        with patch(
            "credential_app.views.render",
            return_value=HttpResponse("rendered"),
        ) as mock_render:
            response = self.dispatch_view(
                CredentialCreateView,
                method="post",
                data=data,
            )

        self.assertEqual(response.status_code, 200)

        form = mock_render.call_args.args[2]["form"]

        self.assertIn("confirm_password", form.errors)
        self.assertFalse(
            Credential.objects.filter(
                vault=self.alice_vault,
                service_name="New Service",
            ).exists()
        )

    def test_create_rejects_category_owned_by_another_user(self):
        data = self.create_form_data(
            category=str(self.bob_category.pk),
        )

        with patch(
            "credential_app.views.render",
            return_value=HttpResponse("rendered"),
        ) as mock_render:
            response = self.dispatch_view(
                CredentialCreateView,
                method="post",
                data=data,
            )

        self.assertEqual(response.status_code, 200)

        form = mock_render.call_args.args[2]["form"]

        self.assertIn("category", form.errors)
        self.assertFalse(
            Credential.objects.filter(
                vault=self.alice_vault,
                service_name="New Service",
            ).exists()
        )

    # ---------------------------------------------------------
    # Update
    # ---------------------------------------------------------

    def test_update_changes_metadata_without_changing_password(self):
        original_ciphertext = (
            self.alice_credential.password_ciphertext
        )

        with patch(
            "credential_app.views.redirect",
            return_value=HttpResponseRedirect("/redirect/"),
        ) as redirect:
            response = self.dispatch_view(
                CredentialUpdateView,
                method="post",
                pk=self.alice_credential.pk,
                data=self.update_form_data(),
            )

        self.assertEqual(response.status_code, 302)

        self.alice_credential.refresh_from_db()

        self.assertEqual(
            self.alice_credential.service_name,
            "GitHub Updated",
        )
        self.assertEqual(
            self.alice_credential.login_username,
            "alice-updated",
        )
        self.assertEqual(
            self.alice_credential.password_ciphertext,
            original_ciphertext,
        )

        redirect.assert_called_once_with(
            "credential_app:detail",
            username="alice",
            vault_slug="personal",
            pk=self.alice_credential.pk,
        )

    def test_update_rejects_another_users_category(self):
        data = self.update_form_data(
            category=str(self.bob_category.pk),
        )
        original_name = self.alice_credential.service_name

        with patch(
            "credential_app.views.render",
            return_value=HttpResponse("rendered"),
        ) as mock_render:
            response = self.dispatch_view(
                CredentialUpdateView,
                method="post",
                pk=self.alice_credential.pk,
                data=data,
            )

        self.assertEqual(response.status_code, 200)

        form = mock_render.call_args.args[2]["form"]
        self.assertIn("category", form.errors)

        self.alice_credential.refresh_from_db()
        self.assertEqual(
            self.alice_credential.service_name,
            original_name,
        )

    # ---------------------------------------------------------
    # Delete
    # ---------------------------------------------------------

    def test_delete_get_shows_confirmation_without_deleting(self):
        with patch(
            "credential_app.views.render",
            return_value=HttpResponse("rendered"),
        ):
            response = self.dispatch_view(
                CredentialDeleteView,
                pk=self.alice_credential.pk,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Credential.objects.filter(
                pk=self.alice_credential.pk,
            ).exists()
        )

    def test_delete_post_deletes_owned_credential(self):
        credential_id = self.alice_credential.pk

        with patch(
            "credential_app.views.redirect",
            return_value=HttpResponseRedirect("/redirect/"),
        ) as redirect:
            response = self.dispatch_view(
                CredentialDeleteView,
                method="post",
                pk=credential_id,
            )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Credential.objects.filter(pk=credential_id).exists()
        )

        redirect.assert_called_once_with(
            "credential_app:list",
            username="alice",
            vault_slug="personal",
        )

    # ---------------------------------------------------------
    # Rotate password
    # ---------------------------------------------------------

    def test_rotate_password_updates_ciphertext_and_history(self):
        old_ciphertext = (
            self.alice_credential.password_ciphertext
        )
        new_password = "New-Strong-Password-456!"

        with (
            patch(
                "credential_app.services.credential_service."
                "EncryptionService.encrypt",
                return_value="rotated-ciphertext",
            ) as encrypt,
            patch(
                "credential_app.views.redirect",
                return_value=HttpResponseRedirect("/redirect/"),
            ),
        ):
            response = self.dispatch_view(
                CredentialRotatePasswordView,
    CredentialRevealPasswordView,
                method="post",
                pk=self.alice_credential.pk,
                data={
                    "new_password": new_password,
                    "confirm_new_password": new_password,
                },
            )

        self.assertEqual(response.status_code, 302)

        self.alice_credential.refresh_from_db()

        self.assertEqual(
            self.alice_credential.password_ciphertext,
            "rotated-ciphertext",
        )
        encrypt.assert_called_once_with(new_password)

        history = CredentialHistory.objects.get(
            credential=self.alice_credential,
        )

        self.assertEqual(
            history.old_password_ciphertext,
            old_ciphertext,
        )
        self.assertEqual(
            history.new_password_ciphertext,
            "rotated-ciphertext",
        )

    def test_rotate_password_rejects_mismatched_confirmation(self):
        original_ciphertext = (
            self.alice_credential.password_ciphertext
        )

        with patch(
            "credential_app.views.render",
            return_value=HttpResponse("rendered"),
        ) as mock_render:
            response = self.dispatch_view(
                CredentialRotatePasswordView,
    CredentialRevealPasswordView,
                method="post",
                pk=self.alice_credential.pk,
                data={
                    "new_password": "New-Strong-Password-456!",
                    "confirm_new_password": "Another-Strong-Password-789!",
                },
            )

        self.assertEqual(response.status_code, 200)

        form = mock_render.call_args.args[2]["form"]
        self.assertIn("confirm_new_password", form.errors)

        self.alice_credential.refresh_from_db()
        self.assertEqual(
            self.alice_credential.password_ciphertext,
            original_ciphertext,
        )
        self.assertFalse(
            CredentialHistory.objects.filter(
                credential=self.alice_credential,
            ).exists()
        )

    # ---------------------------------------------------------
    # Favorite
    # ---------------------------------------------------------

    def test_toggle_favorite_changes_status(self):
        self.assertFalse(self.alice_credential.is_favorite)

        with patch(
            "credential_app.views.redirect",
            return_value=HttpResponseRedirect("/redirect/"),
        ):
            response = self.dispatch_view(
                CredentialToggleFavoriteView,
                method="post",
                pk=self.alice_credential.pk,
            )

        self.assertEqual(response.status_code, 302)

        self.alice_credential.refresh_from_db()
        self.assertTrue(self.alice_credential.is_favorite)

    # ---------------------------------------------------------
    # Move to vault
    # ---------------------------------------------------------

    def test_move_to_vault_moves_credential_to_owned_vault(self):
        with patch(
            "credential_app.views.redirect",
            return_value=HttpResponseRedirect("/redirect/"),
        ) as redirect:
            response = self.dispatch_view(
                CredentialMoveToVaultView,
                method="post",
                pk=self.alice_credential.pk,
                data={
                    "target_vault": str(self.alice_work_vault.pk),
                },
            )

        self.assertEqual(response.status_code, 302)

        self.alice_credential.refresh_from_db()
        self.assertEqual(
            self.alice_credential.vault,
            self.alice_work_vault,
        )

        redirect.assert_called_once_with(
            "credential_app:detail",
            username="alice",
            vault_slug="work",
            pk=self.alice_credential.pk,
        )

    def test_move_to_vault_rejects_another_users_vault(self):
        with (
            patch(
                "credential_app.views.render",
                return_value=HttpResponse("rendered"),
            ) as mock_render,
            patch(
                "credential_app.views.CredentialService.move_to_vault",
            ) as move_service,
        ):
            response = self.dispatch_view(
                CredentialMoveToVaultView,
                method="post",
                pk=self.alice_credential.pk,
                data={
                    "target_vault": str(self.bob_vault.pk),
                },
            )

        self.assertEqual(response.status_code, 200)

        form = mock_render.call_args.args[2]["form"]
        self.assertIn("target_vault", form.errors)
        move_service.assert_not_called()

        self.alice_credential.refresh_from_db()
        self.assertEqual(
            self.alice_credential.vault,
            self.alice_vault,
        )

    def test_move_to_vault_rejects_duplicate_service_name(self):
        Credential.objects.create(
            vault=self.alice_work_vault,
            category=None,
            service_name="GitHub",
            login_username="alice-work-github",
            password_ciphertext="existing-ciphertext",
        )

        with patch(
            "credential_app.views.render",
            return_value=HttpResponse("rendered"),
        ) as mock_render:
            response = self.dispatch_view(
                CredentialMoveToVaultView,
                method="post",
                pk=self.alice_credential.pk,
                data={
                    "target_vault": str(self.alice_work_vault.pk),
                },
            )

        self.assertEqual(response.status_code, 200)

        form = mock_render.call_args.args[2]["form"]
        self.assertIn("target_vault", form.errors)

        self.alice_credential.refresh_from_db()
        self.assertEqual(
            self.alice_credential.vault,
            self.alice_vault,
        )
