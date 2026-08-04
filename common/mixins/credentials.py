from django.http import Http404

from credential_app.models import Credential
from credential_app.selectors.credential_selector import CredentialSelector

class CredentialObjectMixin:
    """
    Provides helper methods for retrieving credentials that belong
    to the authenticated user.
    """
    def get_credential(self):
        credential = CredentialSelector.get_by_id(credential_id=self.kwargs["pk"])

        if credential.vault.user != self.request.user.id:
            raise Http404

        return credential
