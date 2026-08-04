from django.http import Http404
from vault_app.models import Vault

class VaultObjectMixin:
    """
    Provides helper methods for retrieving vaults
    owned by the authenticated user.
    """
    def get_vault(self):
        try:
            return Vault.objects.get(
                pk=self.kwargs["vault_id"],
                user=self.request.user
            )
        except Vault.DoesNotExist:
            raise Http404
