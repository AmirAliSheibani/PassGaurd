
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from vault_app.models import Category, Vault


User = get_user_model()


class VaultViewTests(TestCase):
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
            description="Alice personal vault",
        )
        cls.bob_vault = Vault.objects.create(
            user=cls.bob,
            name="Personal",
            slug="personal",
            description="Bob personal vault",
        )

    def setUp(self):
        self.client.force_login(self.alice)

    def vault_url(self, name, vault=None):
        vault = vault or self.alice_vault

        return reverse(
            f"vault_app:{name}",
            kwargs={
                "username": vault.user.username,
                "vault_slug": vault.slug,
            },
        )

    def test_vault_list_shows_only_current_users_vaults(self):
        response = self.client.get(
            reverse("vault_app:list")
        )

        self.assertEqual(response.status_code, 200)

        vaults = list(response.context["vaults"])

        self.assertIn(self.alice_vault, vaults)
        self.assertNotIn(self.bob_vault, vaults)

    def test_owner_can_view_own_vault(self):
        response = self.client.get(
            self.vault_url("detail")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["vault"],
            self.alice_vault,
        )

    def test_user_cannot_view_another_users_vault(self):
        response = self.client.get(
            self.vault_url("detail", self.bob_vault)
        )

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_update_another_users_vault(self):
        response = self.client.post(
            self.vault_url("update", self.bob_vault),
            {
                "name": "Hacked Vault",
                "description": "Unauthorized change",
                "is_default": "",
            },
        )

        self.assertEqual(response.status_code, 404)

        self.bob_vault.refresh_from_db()
        self.assertEqual(self.bob_vault.name, "Personal")
        self.assertEqual(
            self.bob_vault.description,
            "Bob personal vault",
        )

    def test_user_cannot_delete_another_users_vault(self):
        response = self.client.post(
            self.vault_url("delete", self.bob_vault)
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            Vault.objects.filter(pk=self.bob_vault.pk).exists()
        )

    def test_create_vault_creates_record_for_current_user(self):
        response = self.client.post(
            reverse("vault_app:create"),
            {
                "name": "Work Vault",
                "description": "Work accounts",
                "is_default": "",
            },
        )

        self.assertEqual(response.status_code, 302)

        vault = Vault.objects.get(
            user=self.alice,
            name="Work vault",
        )

        self.assertEqual(vault.description, "Work accounts")
        self.assertTrue(vault.slug)
        self.assertEqual(
            response.url,
            self.vault_url("detail", vault),
        )

    def test_update_vault_preserves_slug(self):
        original_slug = self.alice_vault.slug

        response = self.client.post(
            self.vault_url("update"),
            {
                "name": "Updated Personal",
                "description": "Updated description",
                "is_default": "",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.alice_vault.refresh_from_db()

        self.assertEqual(
            self.alice_vault.name,
            "Updated personal",
        )
        self.assertEqual(
            self.alice_vault.description,
            "Updated description",
        )
        self.assertEqual(
            self.alice_vault.slug,
            original_slug,
        )

    def test_get_delete_confirmation_does_not_delete_vault(self):
        response = self.client.get(
            self.vault_url("delete")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Vault.objects.filter(pk=self.alice_vault.pk).exists()
        )

    def test_post_delete_removes_owned_vault(self):
        vault_id = self.alice_vault.pk

        response = self.client.post(
            self.vault_url("delete")
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("vault_app:list"),
        )
        self.assertFalse(
            Vault.objects.filter(pk=vault_id).exists()
        )

    def test_vault_pages_require_authentication(self):
        self.client.logout()

        urls = [
            reverse("vault_app:list"),
            reverse("vault_app:create"),
            self.vault_url("detail"),
            self.vault_url("update"),
            self.vault_url("delete"),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)


class CategoryViewTests(TestCase):
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

        cls.alice_category = Category.objects.create(
            user=cls.alice,
            name="Social",
        )
        cls.bob_category = Category.objects.create(
            user=cls.bob,
            name="Social",
        )

    def setUp(self):
        self.client.force_login(self.alice)

    def category_url(self, name, category=None):
        category = category or self.alice_category

        return reverse(
            f"vault_app:{name}",
            kwargs={"category_id": category.pk},
        )

    def test_category_list_shows_only_current_users_categories(self):
        response = self.client.get(
            reverse("vault_app:categories")
        )

        self.assertEqual(response.status_code, 200)

        categories = list(response.context["categories"])

        self.assertIn(self.alice_category, categories)
        self.assertNotIn(self.bob_category, categories)

    def test_create_category_creates_record_for_current_user(self):
        response = self.client.post(
            reverse("vault_app:category_create"),
            {
                "name": "Work",
                "color": "#112233",
            },
        )

        self.assertEqual(response.status_code, 302)

        category = Category.objects.get(
            user=self.alice,
            name="Work",
        )

        self.assertEqual(category.color, "#112233")
        self.assertEqual(
            response.url,
            reverse("vault_app:categories"),
        )

    def test_update_category_changes_owned_category(self):
        response = self.client.post(
            self.category_url("category_update"),
            {
                "name": "Work",
                "color": "#112233",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.alice_category.refresh_from_db()

        self.assertEqual(self.alice_category.name, "Work")
        self.assertEqual(self.alice_category.color, "#112233")

    def test_user_cannot_update_another_users_category(self):
        response = self.client.post(
            self.category_url(
                "category_update",
                self.bob_category,
            ),
            {
                "name": "Hacked",
                "color": "#112233",
            },
        )

        self.assertEqual(response.status_code, 404)

        self.bob_category.refresh_from_db()
        self.assertEqual(self.bob_category.name, "Social")

    def test_user_cannot_delete_another_users_category(self):
        response = self.client.post(
            self.category_url(
                "category_delete",
                self.bob_category,
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            Category.objects.filter(pk=self.bob_category.pk).exists()
        )

    def test_get_delete_confirmation_does_not_delete_category(self):
        response = self.client.get(
            self.category_url("category_delete")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Category.objects.filter(pk=self.alice_category.pk).exists()
        )

    def test_post_delete_removes_owned_category(self):
        category_id = self.alice_category.pk

        response = self.client.post(
            self.category_url("category_delete")
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("vault_app:categories"),
        )
        self.assertFalse(
            Category.objects.filter(pk=category_id).exists()
        )

    def test_category_pages_require_authentication(self):
        self.client.logout()

        urls = [
            reverse("vault_app:categories"),
            reverse("vault_app:category_create"),
            self.category_url("category_update"),
            self.category_url("category_delete"),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
