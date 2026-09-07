from vault_app.selectors.vault_selector import VaultSelector


class VaultObjectMixin:
    """
    Provides helper methods for retrieving vaults
    owned by the authenticated user.
    """
    def get_vault(self):
        return VaultSelector.get_by_username_and_slug_for_user(
            username=self.kwargs["username"],
            vault_slug=self.kwargs["vault_slug"],
            user=self.request.user
        )
