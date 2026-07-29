from django.db import transaction

from .encryption_service import EncryptionService
from ..models import Credential


class CredentialService:

    @classmethod
    @transaction.atomic
    def create(cls, *, vault, data):
        """
        Create a new credential with an encrypted password.
        """
        payload = data.copy()

        plaintext_password = payload.pop("password") # Removing plain text password from payload
        payload["password_ciphertext"] = EncryptionService.encrypt(plaintext_password)

        credential = Credential.objects.create(
            vault=vault,
            **data
        )
        return credential