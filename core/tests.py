from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from credential_app.models import Credential
from vault_app.models import Category, Vault

User = get_user_model()


class HomePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="dashboard-user",
            password="Strong-Test-Password-123!",
            recovery_setup_completed=True,
        )
        cls.vault = Vault.objects.create(
            user=cls.user,
            name="Personal",
            slug="personal",
            description="Personal credentials",
            is_default=True,
        )
        cls.category = Category.objects.create(
            user=cls.user,
            name="Development",
            color="#2563EB",
        )
        cls.credential = Credential.objects.create(
            vault=cls.vault,
            category=cls.category,
            service_name="GitHub",
            service_url="https://github.com",
            login_username="dashboard-user",
            login_email="dashboard@example.com",
            password_ciphertext="test-ciphertext-never-rendered",
        )

    def test_root_url_resolves_to_the_real_home_view_and_template(self):
        match = resolve("/")
        self.assertEqual(match.view_name, "core:home")

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")
        self.assertContains(response, "Your credentials, organized.")
        self.assertNotContains(response, "Hello world!")
        self.assertNotContains(response, "test hello world")

    def test_authenticated_root_renders_dashboard_with_real_counts(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")
        self.assertEqual(response.context["vault_count"], 1)
        self.assertEqual(response.context["total_credential_count"], 1)
        self.assertEqual(response.context["category_count"], 1)
        self.assertContains(response, "Your workspace")
        self.assertContains(response, "Personal")
        self.assertContains(response, "GitHub")
        self.assertNotContains(response, "test-ciphertext-never-rendered")
