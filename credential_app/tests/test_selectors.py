
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from credential_app.models import Credential
from credential_app.selectors.credential_selector import CredentialSelector
from vault_app.models import Category, Vault


User = get_user_model()


class CredentialSelectorTests(TestCase):
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

        cls.social_category = Category.objects.create(
            user=cls.alice,
            name="Social",
        )
        cls.work_category = Category.objects.create(
            user=cls.alice,
            name="Work",
        )
        cls.bob_category = Category.objects.create(
            user=cls.bob,
            name="Social",
        )

        cls.github = Credential.objects.create(
            vault=cls.alice_vault,
            category=cls.social_category,
            service_name="GitHub",
            service_url="https://github.com",
            login_username="alice-dev",
            login_email="alice@example.com",
            password_ciphertext="encrypted-github-password",
        )
        cls.mail = Credential.objects.create(
            vault=cls.alice_vault,
            category=None,
            service_name="Mail",
            login_username="alice-mail",
            login_email="mail@example.com",
            password_ciphertext="encrypted-mail-password",
        )
        cls.gitlab = Credential.objects.create(
            vault=cls.alice_work_vault,
            category=cls.work_category,
            service_name="GitLab",
            login_username="alice-work",
            login_email="work@example.com",
            password_ciphertext="encrypted-gitlab-password",
        )
        cls.bob_github = Credential.objects.create(
            vault=cls.bob_vault,
            category=cls.bob_category,
            service_name="GitHub",
            login_username="bob-dev",
            login_email="bob@example.com",
            password_ciphertext="encrypted-bob-password",
        )

        cls.github.is_favorite = True
        cls.github.save(update_fields=["is_favorite"])

        cls.bob_github.is_favorite = True
        cls.bob_github.save(update_fields=["is_favorite"])

    def test_get_by_id_returns_credential(self):
        credential = CredentialSelector.get_by_id(
            self.github.pk,
        )

        self.assertEqual(credential, self.github)

    def test_get_by_id_for_user_returns_owned_credential(self):
        credential = CredentialSelector.get_by_id_for_user(
            self.github.pk,
            self.alice.pk,
        )

        self.assertEqual(credential, self.github)

    def test_get_by_id_for_user_rejects_another_users_credential(self):
        with self.assertRaises(Credential.DoesNotExist):
            CredentialSelector.get_by_id_for_user(
                self.bob_github.pk,
                self.alice.pk,
            )

    def test_get_by_vault_returns_only_vault_credentials(self):
        credentials = CredentialSelector.get_by_vault(
            vault=self.alice_vault,
        )

        self.assertSetEqual(
            set(credentials.values_list("pk", flat=True)),
            {self.github.pk, self.mail.pk},
        )

    def test_get_favorites_returns_only_favorites_in_vault(self):
        favorites = CredentialSelector.get_favorites(
            self.alice_vault,
        )

        self.assertSetEqual(
            set(favorites.values_list("pk", flat=True)),
            {self.github.pk},
        )

    def test_search_matches_service_name_case_insensitively(self):
        results = CredentialSelector.search(
            vault=self.alice_vault,
            user_id=self.alice.pk,
            query="gItHuB",
        )

        self.assertIn(self.github, results)
        self.assertNotIn(self.bob_github, results)

    def test_search_matches_login_username(self):
        results = CredentialSelector.search(
            vault=self.alice_vault,
            user_id=self.alice.pk,
            query="alice-dev",
        )

        self.assertIn(self.github, results)

    def test_search_matches_login_email(self):
        results = CredentialSelector.search(
            vault=self.alice_vault,
            user_id=self.alice.pk,
            query="mail@example.com",
        )

        self.assertIn(self.mail, results)

    def test_search_matches_category_name(self):
        results = CredentialSelector.search(
            vault=self.alice_vault,
            user_id=self.alice.pk,
            query="Social",
        )

        self.assertIn(self.github, results)

    def test_search_is_scoped_to_selected_vault(self):
        results = CredentialSelector.search(
            vault=self.alice_vault,
            user_id=self.alice.pk,
            query="GitLab",
        )

        self.assertNotIn(self.gitlab, results)

    def test_search_does_not_return_another_users_credentials(self):
        results = CredentialSelector.search(
            vault=self.alice_vault,
            user_id=self.alice.pk,
            query="GitHub",
        )

        self.assertNotIn(self.bob_github, results)

    def test_exists_by_name_is_scoped_to_vault(self):
        self.assertTrue(
            CredentialSelector.exists_by_name(
                vault=self.alice_vault,
                service_name="GitHub",
            )
        )

        self.assertFalse(
            CredentialSelector.exists_by_name(
                vault=self.alice_vault,
                service_name="GitLab",
            )
        )

    def test_count_returns_number_of_credentials_in_vault(self):
        self.assertEqual(
            CredentialSelector.count(self.alice_vault),
            2,
        )

        self.assertEqual(
            CredentialSelector.count(self.alice_work_vault),
            1,
        )

    def test_get_recent_orders_by_updated_at(self):
        now = timezone.now()

        Credential.objects.filter(pk=self.github.pk).update(
            updated_at=now - timedelta(days=1),
        )
        Credential.objects.filter(pk=self.mail.pk).update(
            updated_at=now,
        )

        results = list(
            CredentialSelector.get_recent(
                self.alice_vault,
            )
        )

        self.assertEqual(results[0], self.mail)
        self.assertEqual(results[1], self.github)
