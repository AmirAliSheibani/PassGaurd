
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from credential_app.exceptions import DuplicateCredential
from credential_app.models import Credential, CredentialHistory
from credential_app.services.credential_service import CredentialService
from vault_app.models import Category, Vault


User = get_user_model()


class CredentialServiceTests(TestCase):
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

        cls.category = Category.objects.create(
            user=cls.alice,
            name="Social",
        )

    def create_credential(
        self,
        *,
        vault=None,
        service_name="GitHub",
        password_ciphertext="old-ciphertext",
        is_favorite=False,
    ):
        return Credential.objects.create(
            vault=vault or self.alice_vault,
            category=self.category,
            service_name=service_name,
            service_url="https://github.com",
            login_username="alice-dev",
            login_email="alice@example.com",
            password_ciphertext=password_ciphertext,
            is_favorite=is_favorite,
            notes="Test credential",
        )

    def test_create_encrypts_password_before_saving(self):
        data = {
            "category": self.category,
            "service_name": "GitHub",
            "service_url": "https://github.com",
            "login_username": "alice-dev",
            "login_email": "alice@example.com",
            "password": "plain-secret",
            "notes": "Test credential",
        }

        with patch(
            "credential_app.services.credential_service."
            "EncryptionService.encrypt",
            return_value="ciphertext:plain-secret",
        ) as encrypt:
            credential = CredentialService.create(
                vault=self.alice_vault,
                data=data,
            )

        encrypt.assert_called_once_with("plain-secret")

        self.assertEqual(
            credential.password_ciphertext,
            "ciphertext:plain-secret",
        )
        self.assertNotEqual(
            credential.password_ciphertext,
            "plain-secret",
        )
        self.assertEqual(data["password"], "plain-secret")

    def test_update_changes_metadata_without_changing_password(self):
        credential = self.create_credential()
        original_ciphertext = credential.password_ciphertext

        updated = CredentialService.update(
            credential=credential,
            data={
                "service_name": "GitLab",
                "login_username": "alice-work",
                "password": "attempted-new-password",
                "password_ciphertext": "attempted-ciphertext",
            },
        )

        updated.refresh_from_db()

        self.assertEqual(updated.service_name, "GitLab")
        self.assertEqual(updated.login_username, "alice-work")
        self.assertEqual(
            updated.password_ciphertext,
            original_ciphertext,
        )

    def test_rotate_password_updates_ciphertext_and_creates_history(self):
        credential = self.create_credential(
            password_ciphertext="old-ciphertext",
        )

        with patch(
            "credential_app.services.credential_service."
            "EncryptionService.encrypt",
            return_value="new-ciphertext",
        ) as encrypt:
            updated = CredentialService.rotate_password(
                credential=credential,
                new_password="new-plain-password",
            )

        encrypt.assert_called_once_with("new-plain-password")

        updated.refresh_from_db()

        self.assertEqual(
            updated.password_ciphertext,
            "new-ciphertext",
        )

        history = CredentialHistory.objects.get(
            credential=updated,
        )

        self.assertEqual(
            history.old_password_ciphertext,
            "old-ciphertext",
        )
        self.assertEqual(
            history.new_password_ciphertext,
            "new-ciphertext",
        )

    def test_toggle_favorite_can_enable_and_disable_favorite(self):
        credential = self.create_credential(
            is_favorite=False,
        )

        CredentialService.toggle_favorite(
            credential=credential,
        )
        credential.refresh_from_db()

        self.assertTrue(credential.is_favorite)

        CredentialService.toggle_favorite(
            credential=credential,
        )
        credential.refresh_from_db()

        self.assertFalse(credential.is_favorite)

    def test_move_to_vault_changes_credential_vault(self):
        credential = self.create_credential()

        updated = CredentialService.move_to_vault(
            credential=credential,
            vault=self.alice_work_vault,
        )

        updated.refresh_from_db()

        self.assertEqual(
            updated.vault,
            self.alice_work_vault,
        )

    def test_move_to_vault_rejects_duplicate_service_name(self):
        credential = self.create_credential(
            service_name="GitHub",
        )

        self.create_credential(
            vault=self.alice_work_vault,
            service_name="GitHub",
        )

        with self.assertRaises(DuplicateCredential):
            CredentialService.move_to_vault(
                credential=credential,
                vault=self.alice_work_vault,
            )

        credential.refresh_from_db()

        self.assertEqual(
            credential.vault,
            self.alice_vault,
        )

    def test_move_to_vault_rejects_another_users_vault(self):
        credential = self.create_credential()

        with self.assertRaises(ValueError):
            CredentialService.move_to_vault(
                credential=credential,
                vault=self.bob_vault,
            )

        credential.refresh_from_db()

        self.assertEqual(
            credential.vault,
            self.alice_vault,
        )

    def test_delete_removes_credential_and_its_history(self):
        credential = self.create_credential()

        history = CredentialHistory.objects.create(
            credential=credential,
            old_password_ciphertext="old-ciphertext",
            new_password_ciphertext="new-ciphertext",
        )

        credential_id = credential.pk
        history_id = history.pk

        deleted_id = CredentialService.delete(credential)

        self.assertEqual(deleted_id, credential_id)
        self.assertFalse(
            Credential.objects.filter(pk=credential_id).exists()
        )
        self.assertFalse(
            CredentialHistory.objects.filter(pk=history_id).exists()
        )
