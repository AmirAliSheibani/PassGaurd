
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from vault_app.views import (
    CategoryCreateView,
    CategoryDeleteView,
    CategoryListView,
    CategoryUpdateView,
    VaultCreateView,
    VaultDeleteView,
    VaultDetailView,
    VaultListView,
    VaultUpdateView,
)


class VaultURLTests(SimpleTestCase):
    def assert_route(
        self,
        *,
        name,
        kwargs=None,
        expected_path,
        expected_view,
    ):
        url = reverse(f"vault_app:{name}", kwargs=kwargs)

        self.assertEqual(url, expected_path)

        match = resolve(url)
        self.assertEqual(match.view_name, f"vault_app:{name}")
        self.assertIs(match.func.view_class, expected_view)

    def test_vault_list_url(self):
        self.assert_route(
            name="list",
            expected_path="/vaults/",
            expected_view=VaultListView,
        )

    def test_vault_create_url(self):
        self.assert_route(
            name="create",
            expected_path="/vaults/create/",
            expected_view=VaultCreateView,
        )

    def test_vault_detail_url(self):
        self.assert_route(
            name="detail",
            kwargs={
                "username": "alice",
                "vault_slug": "personal",
            },
            expected_path="/alice/personal/",
            expected_view=VaultDetailView,
        )

    def test_vault_update_url(self):
        self.assert_route(
            name="update",
            kwargs={
                "username": "alice",
                "vault_slug": "personal",
            },
            expected_path="/alice/personal/edit/",
            expected_view=VaultUpdateView,
        )

    def test_vault_delete_url(self):
        self.assert_route(
            name="delete",
            kwargs={
                "username": "alice",
                "vault_slug": "personal",
            },
            expected_path="/alice/personal/delete/",
            expected_view=VaultDeleteView,
        )


class CategoryURLTests(SimpleTestCase):
    def assert_route(
        self,
        *,
        name,
        kwargs=None,
        expected_path,
        expected_view,
    ):
        url = reverse(f"vault_app:{name}", kwargs=kwargs)

        self.assertEqual(url, expected_path)

        match = resolve(url)
        self.assertEqual(match.view_name, f"vault_app:{name}")
        self.assertIs(match.func.view_class, expected_view)

    def test_category_list_url(self):
        self.assert_route(
            name="categories",
            expected_path="/categories/",
            expected_view=CategoryListView,
        )

    def test_category_create_url(self):
        self.assert_route(
            name="category_create",
            expected_path="/categories/create/",
            expected_view=CategoryCreateView,
        )

    def test_category_update_url(self):
        self.assert_route(
            name="category_update",
            kwargs={"category_id": 123},
            expected_path="/categories/123/edit/",
            expected_view=CategoryUpdateView,
        )

    def test_category_delete_url(self):
        self.assert_route(
            name="category_delete",
            kwargs={"category_id": 123},
            expected_path="/categories/123/delete/",
            expected_view=CategoryDeleteView,
        )
