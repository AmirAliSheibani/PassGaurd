
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from vault_app.models import Category, Vault


User = get_user_model()


class VaultModelTests(TestCase):
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
        slug="",
        is_default=False,
    ):
        return Vault.objects.create(
            user=user or self.user,
            name=name,
            slug=slug,
            description="",
            is_default=is_default,
        )

    def test_vault_can_be_created(self):
        vault = self.create_vault()

        self.assertEqual(vault.user, self.user)
        self.assertEqual(vault.name, "Personal vault")
        self.assertTrue(vault.slug)
        self.assertFalse(vault.is_default)

    def test_slug_is_generated_when_missing(self):
        vault = self.create_vault(name="Personal Vault")

        self.assertEqual(vault.slug, "personal-vault")

    def test_non_ascii_vault_name_still_gets_a_valid_url_slug(self):
        vault = self.create_vault(name="شخصی")

        self.assertRegex(vault.slug, r"^vault-[0-9a-f]{8}$")

    def test_slug_remains_stable_when_name_changes(self):
        vault = self.create_vault(name="Personal Vault")
        original_slug = vault.slug

        vault.name = "Work Vault"
        vault.save()

        self.assertEqual(vault.slug, original_slug)

    def test_name_is_normalized(self):
        vault = self.create_vault(name="  MY    VAULT  ")

        self.assertEqual(vault.name, "My vault")

    def test_duplicate_vault_name_is_rejected_for_same_user(self):
        self.create_vault(name="Personal", slug="personal-first")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_vault(
                    name="Personal",
                    slug="personal-second",
                )

    def test_vault_name_uniqueness_is_case_insensitive_per_user(self):
        self.create_vault(name="Personal", slug="personal-first")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_vault(name="personal", slug="personal-second")

    def test_same_vault_name_is_allowed_for_different_users(self):
        first_vault = self.create_vault(
            user=self.user,
            name="Personal",
            slug="alice-personal",
        )
        second_vault = self.create_vault(
            user=self.other_user,
            name="Personal",
            slug="bob-personal",
        )

        self.assertEqual(first_vault.name, second_vault.name)
        self.assertNotEqual(first_vault.user, second_vault.user)

    def test_duplicate_slug_is_rejected_for_same_user(self):
        self.create_vault(name="Personal", slug="shared-slug")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_vault(
                    name="Work",
                    slug="shared-slug",
                )

    def test_same_slug_is_allowed_for_different_users(self):
        first_vault = self.create_vault(
            user=self.user,
            name="Personal",
            slug="shared-slug",
        )
        second_vault = self.create_vault(
            user=self.other_user,
            name="Personal",
            slug="shared-slug",
        )

        self.assertEqual(first_vault.slug, second_vault.slug)
        self.assertNotEqual(first_vault.user, second_vault.user)

    def test_user_cannot_have_two_default_vaults(self):
        self.create_vault(
            name="Personal",
            slug="personal",
            is_default=True,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_vault(
                    name="Work",
                    slug="work",
                    is_default=True,
                )

    def test_different_users_can_have_default_vaults(self):
        first_vault = self.create_vault(
            user=self.user,
            name="Personal",
            slug="alice-personal",
            is_default=True,
        )
        second_vault = self.create_vault(
            user=self.other_user,
            name="Personal",
            slug="bob-personal",
            is_default=True,
        )

        self.assertTrue(first_vault.is_default)
        self.assertTrue(second_vault.is_default)


class CategoryModelTests(TestCase):
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

    def test_category_can_be_created(self):
        category = Category.objects.create(
            user=self.user,
            name="Social",
        )

        self.assertEqual(category.user, self.user)
        self.assertEqual(category.name, "Social")
        self.assertEqual(category.color, "#6B7280")

    def test_duplicate_category_name_is_rejected_for_same_user(self):
        Category.objects.create(
            user=self.user,
            name="Social",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(
                    user=self.user,
                    name="Social",
                )

    def test_category_name_uniqueness_is_case_insensitive_per_user(self):
        Category.objects.create(user=self.user, name="Social")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(user=self.user, name="social")

    def test_same_category_name_is_allowed_for_different_users(self):
        first_category = Category.objects.create(
            user=self.user,
            name="Social",
        )
        second_category = Category.objects.create(
            user=self.other_user,
            name="Social",
        )

        self.assertEqual(first_category.name, second_category.name)
        self.assertNotEqual(first_category.user, second_category.user)
