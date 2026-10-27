
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from credential_app.models import Credential, CredentialHistory
from vault_app.models import Category, Vault


User = get_user_model()


class CredentialModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="alice",
            password="test-password",
        )
        cls.other_user = User.objects.create_user(
            username="bob",
            password="test-password",
        )

        cls.vault = Vault.objects.create(
            user=cls.user,
            name="Personal vault",
            slug="personal",
            description="",
        )
        cls.other_vault = Vault.objects.create(
            user=cls.user,
            name="Work vault",
            slug="work",
            description="",
        )
        cls.other_users_vault = Vault.objects.create(
            user=cls.other_user,
            name="Personal vault",
            slug="personal",
            description="",
        )

        cls.category = Category.objects.create(
            user=cls.user,
            name="Social",
        )

    def create_credential(
        self,
        *,
        vault=None,
        category=None,
        service_name="GitHub",
    ):
        if category is None:
            category = self.category

        return Credential.objects.create(
            vault=vault or self.vault,
            category=category,
            service_name=service_name,
            service_url="https://github.com",
            login_username="alice",
            login_email="alice@example.com",
            password_ciphertext="encrypted-password",
            notes="Test credential",
        )

    def test_credential_can_be_created(self):
        credential = self.create_credential()

        self.assertEqual(credential.vault, self.vault)
        self.assertEqual(credential.category, self.category)
        self.assertEqual(credential.service_name, "GitHub")
        self.assertEqual(
            credential.password_ciphertext,
            "encrypted-password",
        )

    def test_credential_is_not_favorite_by_default(self):
        credential = self.create_credential()

        self.assertFalse(credential.is_favorite)

    def test_credential_can_exist_without_category(self):
        credential = Credential.objects.create(
            vault=self.vault,
            category=None,
            service_name="Email",
            login_username="alice",
            password_ciphertext="encrypted-password",
        )

        self.assertIsNone(credential.category)

    def test_duplicate_service_name_is_rejected_within_same_vault(self):
        self.create_credential(service_name="GitHub")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_credential(service_name="GitHub")

    def test_service_name_uniqueness_is_case_insensitive_within_a_vault(self):
        self.create_credential(service_name="GitHub")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_credential(service_name="github")

    def test_same_service_name_is_allowed_in_different_vaults(self):
        first = self.create_credential(
            vault=self.vault,
            service_name="GitHub",
        )
        second = self.create_credential(
            vault=self.other_vault,
            service_name="GitHub",
        )

        self.assertEqual(first.service_name, second.service_name)
        self.assertNotEqual(first.vault, second.vault)

    def test_category_deletion_sets_credential_category_to_null(self):
        credential = self.create_credential()

        self.category.delete()
        credential.refresh_from_db()

        self.assertIsNone(credential.category)

    def test_deleting_credential_deletes_its_history(self):
        credential = self.create_credential()

        history = CredentialHistory.objects.create(
            credential=credential,
            old_password_ciphertext="old-encrypted-password",
            new_password_ciphertext="new-encrypted-password",
        )

        credential_id = credential.pk
        history_id = history.pk

        credential.delete()

        self.assertFalse(
            Credential.objects.filter(pk=credential_id).exists()
        )
        self.assertFalse(
            CredentialHistory.objects.filter(pk=history_id).exists()
        )

    def test_deleting_vault_deletes_credentials_and_history(self):
        credential = self.create_credential()

        history = CredentialHistory.objects.create(
            credential=credential,
            old_password_ciphertext="old-encrypted-password",
            new_password_ciphertext="new-encrypted-password",
        )

        credential_id = credential.pk
        history_id = history.pk
        vault_id = self.vault.pk

        self.vault.delete()

        self.assertFalse(
            Vault.objects.filter(pk=vault_id).exists()
        )
        self.assertFalse(
            Credential.objects.filter(pk=credential_id).exists()
        )
        self.assertFalse(
            CredentialHistory.objects.filter(pk=history_id).exists()
        )

    def test_credential_string_representation(self):
        credential = self.create_credential()

        self.assertEqual(
            str(credential),
            "alice | Personal vault | GitHub",
        )
