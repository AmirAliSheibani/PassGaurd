
from django.contrib.auth import get_user_model
from django.test import TestCase

from vault_app.models import Category, Vault
from vault_app.selectors.vault_selector import CategorySelector, VaultSelector


User = get_user_model()


class VaultSelectorTests(TestCase):
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

        cls.alice_default_vault = Vault.objects.create(
            user=cls.alice,
            name="Personal Vault",
            slug="personal",
            description="Alice's personal vault",
            is_default=True,
        )
        cls.alice_work_vault = Vault.objects.create(
            user=cls.alice,
            name="Work Vault",
            slug="work",
            description="Alice's work vault",
        )
        cls.bob_default_vault = Vault.objects.create(
            user=cls.bob,
            name="Personal Vault",
            slug="personal",
            description="Bob's personal vault",
            is_default=True,
        )

    def test_get_by_id_for_user_returns_owned_vault(self):
        vault = VaultSelector.get_by_id_for_user(
            vault_id=self.alice_default_vault.pk,
            user_id=self.alice.pk,
        )

        self.assertEqual(vault, self.alice_default_vault)

    def test_get_by_id_for_user_rejects_another_users_vault(self):
        with self.assertRaises(Vault.DoesNotExist):
            VaultSelector.get_by_id_for_user(
                vault_id=self.alice_default_vault.pk,
                user_id=self.bob.pk,
            )

    def test_get_by_username_and_slug_returns_correct_vault(self):
        vault = VaultSelector.get_by_username_and_slug_for_user(
            username="alice",
            vault_slug="personal",
            user=self.alice,
        )

        self.assertEqual(vault, self.alice_default_vault)

    def test_username_mismatch_does_not_return_another_users_vault(self):
        with self.assertRaises(Vault.DoesNotExist):
            VaultSelector.get_by_username_and_slug_for_user(
                username="bob",
                vault_slug="personal",
                user=self.alice,
            )

    def test_get_user_vaults_returns_only_owned_vaults(self):
        vaults = VaultSelector.get_user_vaults(
            user_id=self.alice.pk,
        )

        self.assertSetEqual(
            set(vaults.values_list("pk", flat=True)),
            {
                self.alice_default_vault.pk,
                self.alice_work_vault.pk,
            },
        )

    def test_get_by_default_returns_users_default_vault(self):
        vault = VaultSelector.get_by_default(
            user_id=self.alice.pk,
        )

        self.assertEqual(vault, self.alice_default_vault)

    def test_exists_by_name_is_scoped_to_user(self):
        self.assertTrue(
            VaultSelector.exists_by_name(
                vault_name="Personal vault",
                user_id=self.alice.pk,
            )
        )

        self.assertFalse(
            VaultSelector.exists_by_name(
                vault_name="Nonexistent vault",
                user_id=self.alice.pk,
            )
        )

    def test_count_returns_only_users_vaults(self):
        self.assertEqual(
            VaultSelector.count(user_id=self.alice.pk),
            2,
        )
        self.assertEqual(
            VaultSelector.count(user_id=self.bob.pk),
            1,
        )


class CategorySelectorTests(TestCase):
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

        cls.alice_social_category = Category.objects.create(
            user=cls.alice,
            name="Social",
        )
        cls.alice_work_category = Category.objects.create(
            user=cls.alice,
            name="Work",
        )
        cls.bob_social_category = Category.objects.create(
            user=cls.bob,
            name="Social",
        )

    def test_get_by_id_for_user_returns_owned_category(self):
        category = CategorySelector.get_by_id_for_user(
            category_id=self.alice_social_category.pk,
            user_id=self.alice.pk,
        )

        self.assertEqual(category, self.alice_social_category)

    def test_get_by_id_for_user_rejects_another_users_category(self):
        with self.assertRaises(Category.DoesNotExist):
            CategorySelector.get_by_id_for_user(
                category_id=self.alice_social_category.pk,
                user_id=self.bob.pk,
            )

    def test_get_user_categories_returns_only_owned_categories(self):
        categories = CategorySelector.get_user_categories(
            user_id=self.alice.pk,
        )

        self.assertSetEqual(
            set(categories.values_list("pk", flat=True)),
            {
                self.alice_social_category.pk,
                self.alice_work_category.pk,
            },
        )

    def test_exists_by_name_is_scoped_to_user(self):
        self.assertTrue(
            CategorySelector.exists_by_name(
                category_name="Social",
                user_id=self.alice.pk,
            )
        )

        self.assertFalse(
            CategorySelector.exists_by_name(
                category_name="Nonexistent",
                user_id=self.alice.pk,
            )
        )

    def test_count_returns_only_users_categories(self):
        self.assertEqual(
            CategorySelector.count(user_id=self.alice.pk),
            2,
        )
        self.assertEqual(
            CategorySelector.count(user_id=self.bob.pk),
            1,
        )
