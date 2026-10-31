from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from credential_app.models import Credential
from credential_app.selectors.credential_selector import CredentialSelector
from credential_app.views import CredentialListView, GlobalCredentialListView
from vault_app.models import Category, Vault

User = get_user_model()


class GlobalCredentialSearchTests(TestCase):
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
            name="Personal",
            slug="personal",
            description="",
        )

        cls.social = Category.objects.create(user=cls.alice, name="Social")

        cls.github = Credential.objects.create(
            vault=cls.personal,
            category=cls.social,
            service_name="GitHub",
            service_url="https://github.com",
            login_username="alice-dev",
            login_email="alice@example.com",
            password_ciphertext="ciphertext-secret-search-must-not-find",
            notes="private-note-search-must-not-find",
        )
        cls.gitlab = Credential.objects.create(
            vault=cls.work,
            service_name="GitLab",
            service_url="https://gitlab.com",
            login_username="alice-work",
            login_email="work@example.com",
            password_ciphertext="other-ciphertext",
            notes="another-private-note",
        )
        cls.bob_github = Credential.objects.create(
            vault=cls.bob_vault,
            service_name="GitHub",
            service_url="https://github.com",
            login_username="bob-dev",
            login_email="bob@example.com",
            password_ciphertext="bob-ciphertext",
        )

    def test_global_search_finds_credentials_across_vaults(self):
        results = CredentialSelector.search_for_user(
            user_id=self.alice.pk,
            query="Git",
        )

        self.assertSetEqual(
            set(results.values_list("pk", flat=True)),
            {self.github.pk, self.gitlab.pk},
        )

    def test_global_search_matches_vault_name(self):
        results = CredentialSelector.search_for_user(
            user_id=self.alice.pk,
            query="Work",
        )
        self.assertIn(self.gitlab, results)
        self.assertNotIn(self.github, results)

    def test_global_search_never_searches_password_ciphertext_or_notes(self):
        password_results = CredentialSelector.search_for_user(
            user_id=self.alice.pk,
            query="ciphertext-secret-search-must-not-find",
        )
        notes_results = CredentialSelector.search_for_user(
            user_id=self.alice.pk,
            query="private-note-search-must-not-find",
        )

        self.assertFalse(password_results.exists())
        self.assertFalse(notes_results.exists())

    def test_global_search_is_scoped_to_the_current_user(self):
        results = CredentialSelector.search_for_user(
            user_id=self.alice.pk,
            query="GitHub",
        )
        self.assertIn(self.github, results)
        self.assertNotIn(self.bob_github, results)

    def test_global_search_returns_all_owned_credentials_for_empty_query(self):
        results = CredentialSelector.search_for_user(
            user_id=self.alice.pk,
            query="",
        )
        self.assertSetEqual(
            set(results.values_list("pk", flat=True)),
            {self.github.pk, self.gitlab.pk},
        )

    def test_global_view_exposes_all_vaults_and_scoped_results(self):
        request = RequestFactory().get("/credentials/", {"q": "GitLab"})
        request.user = self.alice

        view = GlobalCredentialListView()
        view.setup(request)
        context = view.get_context_data()

        self.assertEqual(context["show_vault_column"], True)
        self.assertEqual(context["result_count"], 1)
        self.assertEqual(list(context["credentials"]), [self.gitlab])
        self.assertIsNone(context["vault"])

    def test_local_view_remains_scoped_to_selected_vault(self):
        request = RequestFactory().get("/vault/alice/personal/credentials/", {"q": "Git"})
        request.user = self.alice

        view = CredentialListView()
        view.setup(request, username="alice", vault_slug="personal")
        context = view.get_context_data()

        self.assertEqual(context["result_count"], 1)
        self.assertEqual(list(context["credentials"]), [self.github])
        self.assertFalse(context["show_vault_column"])
