from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from common.security.reauthentication import InvalidMasterPassword
from credential_app.exceptions import (
    CredentialOwnershipMismatch,
    DuplicateCredential,
    InvalidCredentialSelection,
    VaultOwnershipMismatch,
)
from credential_app.models import Credential, CredentialHistory
from credential_app.services.credential_service import CredentialService
from vault_app.models import Vault

User = get_user_model()


class BulkCredentialServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(
            username="alice",
            password="Strong-Test-Password-123!",
        )
        cls.bob = User.objects.create_user(
            username="bob",
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
        cls.bob_vault = Vault.objects.create(
            user=cls.bob,
            name="Bob Vault",
            slug="bob-vault",
            description="",
        )

    def create_credential(self, *, vault=None, name="GitHub"):
        return Credential.objects.create(
            vault=vault or self.personal,
            service_name=name,
            login_username="alice",
            password_ciphertext=f"ciphertext-{name}",
        )

    def test_normalize_selection_deduplicates_ids(self):
        self.assertEqual(
            CredentialService.normalize_credential_ids(["4", 4, "5"]),
            [4, 5],
        )

    def test_normalize_selection_rejects_empty_non_numeric_and_zero_ids(self):
        for values in ([], ["x"], [0], [-1], [True], [9223372036854775808]):
            with self.subTest(values=values):
                with self.assertRaises(InvalidCredentialSelection):
                    CredentialService.normalize_credential_ids(values)

    def test_normalize_selection_enforces_bulk_limit(self):
        with self.assertRaises(InvalidCredentialSelection):
            CredentialService.normalize_credential_ids(
                range(1, CredentialService.MAX_BULK_CREDENTIALS + 2)
            )

    def test_bulk_move_moves_all_selected_credentials(self):
        first = self.create_credential(name="GitHub")
        second = self.create_credential(name="GitLab")

        result = CredentialService.bulk_move(
            credential_ids=[first.pk, second.pk],
            user_id=self.alice.pk,
            target_vault_id=self.work.pk,
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(result["moved_count"], 2)
        self.assertEqual(result["unchanged_count"], 0)
        self.assertEqual(first.vault_id, self.work.pk)
        self.assertEqual(second.vault_id, self.work.pk)

    def test_bulk_move_counts_credentials_already_in_target(self):
        source = self.create_credential(name="GitHub")
        unchanged = self.create_credential(vault=self.work, name="GitLab")

        result = CredentialService.bulk_move(
            credential_ids=[source.pk, unchanged.pk],
            user_id=self.alice.pk,
            target_vault_id=self.work.pk,
        )

        self.assertEqual(result["moved_count"], 1)
        self.assertEqual(result["unchanged_count"], 1)

    def test_bulk_move_is_all_or_nothing_on_destination_conflict(self):
        first = self.create_credential(name="GitHub")
        second = self.create_credential(name="GitLab")
        self.create_credential(vault=self.work, name="GitLab")

        with self.assertRaises(DuplicateCredential):
            CredentialService.bulk_move(
                credential_ids=[first.pk, second.pk],
                user_id=self.alice.pk,
                target_vault_id=self.work.pk,
            )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.vault_id, self.personal.pk)
        self.assertEqual(second.vault_id, self.personal.pk)

    def test_bulk_move_rejects_duplicate_names_inside_selection(self):
        first = self.create_credential(vault=self.personal, name="GitHub")
        second = self.create_credential(vault=self.work, name="GitHub")
        destination = Vault.objects.create(
            user=self.alice,
            name="Archive",
            slug="archive",
            description="",
        )

        with self.assertRaises(DuplicateCredential):
            CredentialService.bulk_move(
                credential_ids=[first.pk, second.pk],
                user_id=self.alice.pk,
                target_vault_id=destination.pk,
            )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.vault_id, self.personal.pk)
        self.assertEqual(second.vault_id, self.work.pk)

    def test_bulk_move_rejects_credentials_owned_by_another_user(self):
        alice_credential = self.create_credential(name="GitHub")
        bob_credential = Credential.objects.create(
            vault=self.bob_vault,
            service_name="Bob service",
            login_username="bob",
            password_ciphertext="bob-ciphertext",
        )

        with self.assertRaises(CredentialOwnershipMismatch):
            CredentialService.bulk_move(
                credential_ids=[alice_credential.pk, bob_credential.pk],
                user_id=self.alice.pk,
                target_vault_id=self.work.pk,
            )

        alice_credential.refresh_from_db()
        self.assertEqual(alice_credential.vault_id, self.personal.pk)

    def test_bulk_move_rejects_foreign_destination_vault(self):
        credential = self.create_credential()
        with self.assertRaises(VaultOwnershipMismatch):
            CredentialService.bulk_move(
                credential_ids=[credential.pk],
                user_id=self.alice.pk,
                target_vault_id=self.bob_vault.pk,
            )

    @patch("credential_app.services.credential_service.ReauthenticationService.verify_master_password")
    def test_bulk_delete_removes_selected_credentials_and_history(self, verify_password):
        first = self.create_credential(name="GitHub")
        second = self.create_credential(name="GitLab")
        untouched = self.create_credential(name="Notion")
        history = CredentialHistory.objects.create(
            credential=first,
            old_password_ciphertext="old",
            new_password_ciphertext="new",
        )

        deleted_count = CredentialService.bulk_delete(
            credential_ids=[first.pk, second.pk],
            user=self.alice,
            master_password="correct-master-password",
            ip_address="127.0.0.1",
        )

        verify_password.assert_called_once_with(
            user=self.alice,
            password="correct-master-password",
            action="credential-bulk-delete",
            ip_address="127.0.0.1",
        )
        self.assertEqual(deleted_count, 2)
        self.assertFalse(Credential.objects.filter(pk__in=[first.pk, second.pk]).exists())
        self.assertFalse(CredentialHistory.objects.filter(pk=history.pk).exists())
        self.assertTrue(Credential.objects.filter(pk=untouched.pk).exists())

    @patch(
        "credential_app.services.credential_service.ReauthenticationService.verify_master_password",
        side_effect=InvalidMasterPassword,
    )
    def test_bulk_delete_does_not_delete_if_master_password_is_wrong(self, verify_password):
        credential = self.create_credential()

        with self.assertRaises(InvalidMasterPassword):
            CredentialService.bulk_delete(
                credential_ids=[credential.pk],
                user=self.alice,
                master_password="wrong-password",
            )

        self.assertTrue(Credential.objects.filter(pk=credential.pk).exists())

    @patch("credential_app.services.credential_service.ReauthenticationService.verify_master_password")
    def test_bulk_delete_rejects_foreign_ids_without_deleting_own_records(self, verify_password):
        own = self.create_credential(name="GitHub")
        foreign = Credential.objects.create(
            vault=self.bob_vault,
            service_name="Bob service",
            login_username="bob",
            password_ciphertext="bob-ciphertext",
        )

        with self.assertRaises(CredentialOwnershipMismatch):
            CredentialService.bulk_delete(
                credential_ids=[own.pk, foreign.pk],
                user=self.alice,
                master_password="correct-password",
            )

        self.assertTrue(Credential.objects.filter(pk=own.pk).exists())
        self.assertTrue(Credential.objects.filter(pk=foreign.pk).exists())
