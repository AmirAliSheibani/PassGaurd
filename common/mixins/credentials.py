from django.http import Http404

from credential_app.models import Credential
from credential_app.selectors.credential_selector import CredentialSelector

class CredentialObjectMixin:
    """
    Provides helper methods for retrieving credentials that belong
    to the authenticated user.
    """
    def get_credential(self):
        return CredentialSelector.get_by_id_for_user(
            credential_id=self.kwargs["pk"],
            user_id=self.request.user.id
        )
