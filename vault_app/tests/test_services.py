
from django.contrib.auth import get_user_model
from django.test import TestCase

from vault_app.models import Category, Vault
from vault_app.services.vault_service import CategoryService, VaultService


User = get_user_model()


class VaultServiceTests(TestCase):
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

    def create_vault(
        self,
        *,
        user=None,
        name="Personal Vault",
        slug="personal",
        is_default=False,
    ):
        return Vault.objects.create(
            user=user or self.user,
            name=name,
            slug=slug,
            description="",
            is_default=is_default,
        )

    def test_create_vault(self):
        vault = VaultService.create(
            user=self.user,
            name="Work Vault",
            description="For work accounts",
        )

        self.assertEqual(vault.user, self.user)
        self.assertEqual(vault.description, "For work accounts")
        self.assertTrue(vault.slug)
        self.assertFalse(vault.is_default)

    def test_create_vault_with_slug_collision(self):
        first_vault = VaultService.create(
            user=self.user,
            name="Work Tools",
        )
        second_vault = VaultService.create(
            user=self.user,
            name="Work-Tools",
        )

        self.assertNotEqual(first_vault.slug, second_vault.slug)
        self.assertEqual(first_vault.slug, "work-tools")
        self.assertEqual(second_vault.slug, "work-tools-2")

    def test_create_default_vault_demotes_previous_default(self):
        previous_default = self.create_vault(
            name="Personal",
            slug="personal",
            is_default=True,
        )

        new_default = VaultService.create(
            user=self.user,
            name="Work Vault",
            is_default=True,
        )

        previous_default.refresh_from_db()

        self.assertFalse(previous_default.is_default)
        self.assertTrue(new_default.is_default)

    def test_create_non_default_vault_preserves_current_default(self):
        current_default = self.create_vault(
            name="Personal",
            slug="personal",
            is_default=True,
        )

        VaultService.create(
            user=self.user,
            name="Work Vault",
            is_default=False,
        )

        current_default.refresh_from_db()

        self.assertTrue(current_default.is_default)

    def test_update_vault_changes_fields_and_preserves_slug(self):
        vault = self.create_vault()
        original_slug = vault.slug

        VaultService.update(
            vault=vault,
            name="Work Vault",
            description="Updated description",
            is_default=False,
        )

        vault.refresh_from_db()

        self.assertEqual(vault.name, "Work vault")
        self.assertEqual(vault.description, "Updated description")
        self.assertEqual(vault.slug, original_slug)

    def test_update_to_default_demotes_previous_default(self):
        previous_default = self.create_vault(
            name="Personal",
            slug="personal",
            is_default=True,
        )
        target_vault = self.create_vault(
            name="Work",
            slug="work",
            is_default=False,
        )

        VaultService.update(
            vault=target_vault,
            name="Work",
            description="",
            is_default=True,
        )

        previous_default.refresh_from_db()
        target_vault.refresh_from_db()

        self.assertFalse(previous_default.is_default)
        self.assertTrue(target_vault.is_default)

    def test_delete_vault_removes_record(self):
        vault = self.create_vault()

        VaultService.delete(vault=vault)

        self.assertFalse(
            Vault.objects.filter(pk=vault.pk).exists()
        )


class CategoryServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="alice",
            password="test-password",
        )

    def test_create_category(self):
        category = CategoryService.create(
            user=self.user,
            name="Social",
            color="#FF5733",
        )

        self.assertEqual(category.user, self.user)
        self.assertEqual(category.name, "Social")
        self.assertEqual(category.color, "#FF5733")

    def test_update_category(self):
        category = Category.objects.create(
            user=self.user,
            name="Social",
            color="#6B7280",
        )

        CategoryService.update(
            category=category,
            name="Work",
            color="#112233",
        )

        category.refresh_from_db()

        self.assertEqual(category.name, "Work")
        self.assertEqual(category.color, "#112233")

    def test_delete_category_removes_record(self):
        category = Category.objects.create(
            user=self.user,
            name="Social",
        )

        CategoryService.delete(category=category)

        self.assertFalse(
            Category.objects.filter(pk=category.pk).exists()
        )
