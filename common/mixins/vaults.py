from vault_app.models import Vault, Category
from vault_app.selectors.vault_selector import VaultSelector, CategorySelector
from django.http import Http404

class VaultObjectMixin:
    """
    Provides helper methods for retrieving vaults
    owned by the authenticated user.
    """
    def get_vault(self):
        try:
            return VaultSelector.get_by_username_and_slug_for_user(
                username=self.kwargs["username"],
                vault_slug=self.kwargs["vault_slug"],
                user=self.request.user
            )
        except Vault.DoesNotExist:
            raise Http404


class CategoryObjectMixin:
    """
    Provides helper methods for retrieving categories
    owned by the authenticated user.
    """
    def get_category(self):
        try:
            return CategorySelector.get_by_id_for_user(
                category_id=self.kwargs["category_id"],
                user_id=self.request.user.id,
            )
        except Category.DoesNotExist:
            raise Http404
