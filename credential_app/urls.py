from django.urls import path

from .views import (
    CredentialCreateView,
    GlobalCredentialListView,
    BulkCredentialMoveView,
    BulkCredentialDeleteView,
    CredentialDeleteView,
    CredentialDetailView,
    CredentialListView,
    CredentialMoveToVaultView,
    CredentialRotatePasswordView,
    CredentialRevealPasswordView,
    CredentialToggleFavoriteView,
    CredentialUpdateView,
)

app_name = "credential_app"

urlpatterns = [
    # Global workspace and bulk operations.
    path("credentials/", GlobalCredentialListView.as_view(), name="global_list"),
    path("credentials/bulk/move/", BulkCredentialMoveView.as_view(), name="bulk_move"),
    path("credentials/bulk/delete/", BulkCredentialDeleteView.as_view(), name="bulk_delete"),

    # Vault-scoped list and create. Keep /vault/... URLs stable.
    path("vault/<str:username>/<slug:vault_slug>/credentials/", CredentialListView.as_view(), name="list",),
    path("vault/<str:username>/<slug:vault_slug>/credentials/create/", CredentialCreateView.as_view(), name="create",),

    # Detail and explicit password reveal (POST only).
    path("vault/<str:username>/<slug:vault_slug>/credentials/<int:pk>/", CredentialDetailView.as_view(), name="detail",),
    path("vault/<str:username>/<slug:vault_slug>/credentials/<int:pk>/reveal-password/", CredentialRevealPasswordView.as_view(), name="reveal_password",),

    # Update and delete
    path("vault/<str:username>/<slug:vault_slug>/credentials/<int:pk>/edit/", CredentialUpdateView.as_view(), name="update",),
    path("vault/<str:username>/<slug:vault_slug>/credentials/<int:pk>/delete/", CredentialDeleteView.as_view(), name="delete",),

    # Password rotation
    path("vault/<str:username>/<slug:vault_slug>/credentials/<int:pk>/rotate-password/", CredentialRotatePasswordView.as_view(), name="rotate_password",),

    # Favorite
    path("vault/<str:username>/<slug:vault_slug>/credentials/<int:pk>/toggle-favorite/", CredentialToggleFavoriteView.as_view(), name="toggle_favorite",),

    # Move to another vault
    path("vault/<str:username>/<slug:vault_slug>/credentials/<int:pk>/move-to-vault/", CredentialMoveToVaultView.as_view(), name="move_to_vault",),
]