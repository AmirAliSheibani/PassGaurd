from django.db import transaction

from vault_app.models import Vault
from common.security.encryption.encryption_service import EncryptionService
from credential_app.exceptions import DuplicateCredential
from ..models import Credential, CredentialHistory


class CredentialService:

    @classmethod
    @transaction.atomic
    def create(cls, *, vault: Vault, data: dict) -> Credential:
        """
        Create a new credential with an encrypted password.
        """
        payload = data.copy()

        plaintext_password = payload.pop("password") # Removing plain text password from payload
        payload["password_ciphertext"] = EncryptionService.encrypt(plaintext_password)

        credential = Credential.objects.create(
            vault=vault,
            **payload
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
        payload.pop("password", None)
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


    @classmethod
    @transaction.atomic
    def toggle_favorite(cls, *, credential: Credential) -> Credential:
        """
        update an existing credential favorite.
        """
        credential.is_favorite =(
            not credential.is_favorite
        )
        credential.save(update_fields=["is_favorite", "updated_at"])
        return credential


    @classmethod
    @transaction.atomic
    def move_to_vault(cls, *, credential: Credential, vault: Vault) -> Credential:
        """
        move a credential to another vault
        """
        exists = Credential.objects.filter(
            vault=vault,
            service_name=credential.service_name,
        ).exclude(
            pk=credential.pk
        ).exists() # Each service name for credentials should be unique in each vaults
        if exists:
            raise DuplicateCredential(
                "credential already exists in target vault.",
            )

        credential.vault = vault
        credential.save(update_fields=["vault", "updated_at"])
        return credential


    @classmethod
    @transaction.atomic
    def delete(cls, credential: Credential) -> int:
        """
        delete a credential.
        """
        credential_id = credential.pk
        credential.delete()
        return credential_id

