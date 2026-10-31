from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from common.security.reauthentication import InvalidMasterPassword
from credential_app.models import Credential
from credential_app.views import (
    BulkCredentialDeleteView,
    BulkCredentialMoveView,
    _sign_bulk_delete_selection,
)
from vault_app.models import Vault

User = get_user_model()


class BulkCredentialViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(
            username="alice",
            password="Strong-Test-Password-123!",
        )
        cls.personal = Vault.objects.create(
            user=cls.alice,
            name="Personal",
            slug="personal",
            description="",
        )
        cls.work = Vault.objects.create(
            user=cls.alice,
            name="Work",
            slug="work",
            description="",
        )

    def setUp(self):
        self.factory = RequestFactory()

    def create_credential(self, name):
        return Credential.objects.create(
            vault=self.personal,
            service_name=name,
            login_username="alice",
            password_ciphertext=f"ciphertext-{name}",
        )

    def make_request(self, path, *, data, user=None):
        request = self.factory.post(path, data=data)
        request.user = user or self.alice
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_bulk_move_view_moves_selection_and_returns_to_safe_page(self):
        first = self.create_credential("GitHub")
        second = self.create_credential("GitLab")
        request = self.make_request(
            "/credentials/bulk/move/",
            data={
                "credential_ids": [str(first.pk), str(second.pk)],
                "target_vault": str(self.work.pk),
                "return_to": "/credentials/?q=Git",
            },
        )

        response = BulkCredentialMoveView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/credentials/?q=Git")
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.vault_id, self.work.pk)
        self.assertEqual(second.vault_id, self.work.pk)

    def test_bulk_delete_first_step_renders_review_without_deleting(self):
        credential = self.create_credential("GitHub")
        request = self.make_request(
            "/credentials/bulk/delete/",
            data={
                "credential_ids": [str(credential.pk)],
                "return_to": "/credentials/",
            },
        )

        with patch("credential_app.views.render", return_value=HttpResponse("review")) as render:
            response = BulkCredentialDeleteView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Credential.objects.filter(pk=credential.pk).exists())
        self.assertEqual(render.call_args.args[1], "credential_app/bulk_delete_confirm.html")
        self.assertEqual(
            render.call_args.args[2]["credential_ids"],
            [credential.pk],
        )
        self.assertTrue(render.call_args.args[2]["selection_token"])

    def test_bulk_delete_catches_invalid_master_password_from_security_service(self):
        credential = self.create_credential("GitHub")
        request = self.make_request(
            "/credentials/bulk/delete/",
            data={
                "stage": "confirm",
                "selection_token": _sign_bulk_delete_selection(
                    credential_ids=[credential.pk],
                    user_id=self.alice.pk,
                ),
                "return_to": "/credentials/",
                "master_password": "wrong-password",
                "confirm_delete": "on",
            },
        )

        with patch(
            "credential_app.views.CredentialService.bulk_delete",
            side_effect=InvalidMasterPassword,
        ), patch(
            "credential_app.views.render",
            return_value=HttpResponse("invalid", status=400),
        ) as render:
            response = BulkCredentialDeleteView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Credential.objects.filter(pk=credential.pk).exists())
        form = render.call_args.args[2]["form"]
        self.assertIn("master_password", form.errors)

    def test_bulk_delete_uses_signed_selection_not_client_supplied_ids(self):
        reviewed = self.create_credential("Reviewed")
        tampered = self.create_credential("Not reviewed")
        token = _sign_bulk_delete_selection(
            credential_ids=[reviewed.pk],
            user_id=self.alice.pk,
        )
        request = self.make_request(
            "/credentials/bulk/delete/",
            data={
                "stage": "confirm",
                "selection_token": token,
                "credential_ids": [str(tampered.pk)],
                "return_to": "/credentials/",
                "master_password": "correct-master-password",
                "confirm_delete": "on",
            },
        )

        with patch(
            "credential_app.views.CredentialService.bulk_delete",
            return_value=1,
        ) as bulk_delete:
            response = BulkCredentialDeleteView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            bulk_delete.call_args.kwargs["credential_ids"],
            [reviewed.pk],
        )
        self.assertTrue(Credential.objects.filter(pk=tampered.pk).exists())

    def test_bulk_delete_rejects_expired_or_tampered_selection_token(self):
        credential = self.create_credential("GitHub")
        request = self.make_request(
            "/credentials/bulk/delete/",
            data={
                "stage": "confirm",
                "selection_token": "not-a-valid-signature",
                "return_to": "/credentials/",
                "master_password": "correct-master-password",
                "confirm_delete": "on",
            },
        )

        response = BulkCredentialDeleteView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Credential.objects.filter(pk=credential.pk).exists())

    def test_bulk_delete_route_and_global_search_route_are_registered(self):
        self.assertEqual(reverse("credential_app:global_list"), "/credentials/")
        self.assertEqual(reverse("credential_app:bulk_move"), "/credentials/bulk/move/")
        self.assertEqual(reverse("credential_app:bulk_delete"), "/credentials/bulk/delete/")
