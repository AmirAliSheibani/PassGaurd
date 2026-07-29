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

    @classmethod
    @transaction.atomic
    def update(cls, *, credential: Credential, data: dict,) -> Credential:
        """
        Update an existing credential.
        anything except password
        """
        payload = data.copy()
        plaintext_password = payload.pop("password", None)
        payload.pop("password_ciphertext", None)

        for field, value in payload.items():
            setattr(credential, field, value,)

        credential.save(
            update_fields=[
                *payload.keys(),
                "updated_at",
            ]
        )
        return credential