from django.db import transaction

from .encryption_service import EncryptionService
from ..models import Credential, CredentialHistory


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


    @classmethod
    @transaction.atomic
    def rotate_password(cls, *, credential: Credential, new_password: str) -> Credential:
        """
        update an existing credential password and
        create an object on CredentialHistory to log rotate password.
        """
        old_ciphertext = credential.password_ciphertext
        new_ciphertext = EncryptionService.encrypt(new_password)

        credential.password_ciphertext = new_ciphertext
        credential.save(update_fields=["password_ciphertext", "updated_at"])

        CredentialHistory.objects.create(
            credential=credential,
            old_password_ciphertext=old_ciphertext,
            new_password_ciphertext=new_ciphertext,
        )

        return credential

    