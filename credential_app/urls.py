from django.urls import path

from .views import (
    CredentialCreateView,
    CredentialDeleteView,
    CredentialDetailView,
    CredentialListView,
    CredentialMoveToVaultView,
    CredentialRotatePasswordView,
    CredentialToggleFavoriteView,
    CredentialUpdateView,
)

app_name = "credential_app"

urlpatterns = [
    # List and create
    path("<str:username>/<slug:vault_slug>/credentials/", CredentialListView.as_view(), name="list",),
    path("<str:username>/<slug:vault_slug>/credentials/create/", CredentialCreateView.as_view(), name="create",),

    # Detail
    path("<str:username>/<slug:vault_slug>/credentials/<int:pk>/", CredentialDetailView.as_view(), name="detail",),

    # Update and delete
    path("<str:username>/<slug:vault_slug>/credentials/<int:pk>/edit/", CredentialUpdateView.as_view(), name="update",),
    path("<str:username>/<slug:vault_slug>/credentials/<int:pk>/delete/", CredentialDeleteView.as_view(), name="delete",),

    # Password rotation
    path("<str:username>/<slug:vault_slug>/credentials/<int:pk>/rotate-password/", CredentialRotatePasswordView.as_view(), name="rotate_password",),

    # Favorite
    path("<str:username>/<slug:vault_slug>/credentials/<int:pk>/toggle-favorite/", CredentialToggleFavoriteView.as_view(), name="toggle_favorite",),

    # Move to another vault
    path("<str:username>/<slug:vault_slug>/credentials/<int:pk>/move-to-vault/", CredentialMoveToVaultView.as_view(), name="move_to_vault",),
]