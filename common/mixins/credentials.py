from django.http import Http404

from common.mixins.vaults import VaultObjectMixin
from credential_app.models import Credential
from credential_app.selectors.credential_selector import CredentialSelector

class CredentialInVaultMixin(VaultObjectMixin):
    """
    Retrieves a credential only if it belongs to the authenticated
    user and the vault specified in the URL.
    """

    def get_credential(self) -> Credential:
        vault = self.get_vault()

        try:
            credential = CredentialSelector.get_by_id_for_user(
                credential_id=self.kwargs["pk"],
               user_id=self.request.user.pk,
            )
        except Credential.DoesNotExist:
            raise Http404

        if credential.vault_id != vault.pk:
            raise Http404

        return credential