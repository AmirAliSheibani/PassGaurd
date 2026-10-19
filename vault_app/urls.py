from django.urls import path

from .views import (
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

app_name = "vault_app"

urlpatterns = [
    # Vault list and creation
    path("vaults/", VaultListView.as_view(), name="list"),
    path("vaults/create/", VaultCreateView.as_view(), name="create"),

    # Categories — must come before dynamic vault URLs
    path("categories/", CategoryListView.as_view(), name="categories"),
    path("categories/create/", CategoryCreateView.as_view(), name="category_create"),
    path(
        "categories/<int:category_id>/edit/",
        CategoryUpdateView.as_view(),
        name="category_update",
    ),
    path(
        "categories/<int:category_id>/delete/",
        CategoryDeleteView.as_view(),
        name="category_delete",
    ),

    # Dynamic vault URLs — keep these at the end
    path(
        "<str:username>/<slug:vault_slug>/edit/",
        VaultUpdateView.as_view(),
        name="update",
    ),
    path(
        "<str:username>/<slug:vault_slug>/delete/",
        VaultDeleteView.as_view(),
        name="delete",
    ),
    path(
        "<str:username>/<slug:vault_slug>/",
        VaultDetailView.as_view(),
        name="detail",
    ),
]