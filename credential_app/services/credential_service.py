from collections import Counter
from typing import Iterable

from django.db import IntegrityError, transaction
from django.utils import timezone

from common.security.encryption.encryption_service import EncryptionService
from common.security.reauthentication import ReauthenticationService
from credential_app.exceptions import (
    CredentialOwnershipMismatch,
    DuplicateCredential,
    InvalidCredentialSelection,
    VaultOwnershipMismatch,
)
from credential_app.models import Credential, CredentialHistory
from vault_app.models import Vault


class CredentialService:
    """Credential business operations and their transactional guarantees."""

    MAX_BULK_CREDENTIALS = 100
    CREATE_FIELDS = {
        "category",
        "service_name",
        "service_url",
        "login_username",
        "login_email",
        "is_favorite",
        "notes",
    }
    UPDATE_FIELDS = {
        "category",
        "service_name",
        "service_url",
        "login_username",
        "login_email",
        "is_favorite",
        "notes",
    }

    @classmethod
    def normalize_credential_ids(cls, credential_ids: Iterable) -> list[int]:
        """Validate, de-duplicate and bound IDs received from a bulk form."""
        if isinstance(credential_ids, (str, bytes)):
            credential_ids = [credential_ids]

        normalized = []
        seen = set()
        try:
            for raw_id in credential_ids:
                # Only accept positive integers or canonical ASCII ID strings.
                # Avoid int() silently accepting booleans, floats, signs, or padding.
                if isinstance(raw_id, bool):
                    raise ValueError
                if isinstance(raw_id, int):
                    credential_id = raw_id
                elif isinstance(raw_id, str) and raw_id.isascii() and raw_id.isdigit():
                    if not raw_id or raw_id.startswith("0"):
                        raise ValueError
                    credential_id = int(raw_id)
                else:
                    raise ValueError
                if credential_id < 1 or credential_id > 9223372036854775807:
                    raise ValueError
                if credential_id not in seen:
                    seen.add(credential_id)
                    normalized.append(credential_id)
                if len(normalized) > cls.MAX_BULK_CREDENTIALS:
                    raise InvalidCredentialSelection(
                        f"You can select up to {cls.MAX_BULK_CREDENTIALS} credentials at once."
                    )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, InvalidCredentialSelection):
                raise
            raise InvalidCredentialSelection(
                "The credential selection contains an invalid ID."
            ) from exc

        if not normalized:
            raise InvalidCredentialSelection(
                "Select at least one credential."
            )

        return normalized

    @classmethod
    @transaction.atomic
    def create(cls, *, vault: Vault, data: dict) -> Credential:
        """Create a credential and encrypt its password before persistence."""
        payload = {key: value for key, value in data.items() if key in cls.CREATE_FIELDS}
        plaintext_password = data.get("password")
        if not isinstance(plaintext_password, str) or not plaintext_password:
            raise ValueError("A non-empty password is required to create a credential.")

        if payload.get("category") is not None:
            if payload["category"].user_id != vault.user_id:
                raise VaultOwnershipMismatch(
                    "A credential category must belong to the vault owner."
                )

        service_name = payload.get("service_name")
        if not service_name:
            raise ValueError("Service name is required.")
        if Credential.objects.filter(vault=vault, service_name=service_name).exists():
            raise DuplicateCredential(
                "A credential with this service name already exists in the vault."
            )

        payload["password_ciphertext"] = EncryptionService.encrypt(plaintext_password)
        try:
            with transaction.atomic():
                return Credential.objects.create(vault=vault, **payload)
        except IntegrityError as exc:
            raise DuplicateCredential(
                "A credential with this service name already exists in the vault."
            ) from exc

    @classmethod
    @transaction.atomic
    def update(cls, *, credential: Credential, data: dict) -> Credential:
        """Update only editable metadata; password material is never accepted."""
        payload = {key: value for key, value in data.items() if key in cls.UPDATE_FIELDS}

        if payload.get("category") is not None:
            if payload["category"].user_id != credential.vault.user_id:
                raise VaultOwnershipMismatch(
                    "A credential category must belong to the vault owner."
                )

        new_name = payload.get("service_name")
        if new_name and Credential.objects.filter(
            vault_id=credential.vault_id,
            service_name=new_name,
        ).exclude(pk=credential.pk).exists():
            raise DuplicateCredential(
                "A credential with this service name already exists in the vault."
            )

        for field, value in payload.items():
            setattr(credential, field, value)

        if payload:
            try:
                with transaction.atomic():
                    credential.save(update_fields=[*payload.keys(), "updated_at"])
            except IntegrityError as exc:
                raise DuplicateCredential(
                    "A credential with this service name already exists in the vault."
                ) from exc

        return credential

    @classmethod
    @transaction.atomic
    def rotate_password(cls, *, credential: Credential, new_password: str) -> Credential:
        """Replace an existing credential password and store ciphertext history."""
        if not new_password:
            raise ValueError("A non-empty password is required.")

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
        credential.is_favorite = not credential.is_favorite
        credential.save(update_fields=["is_favorite", "updated_at"])
        return credential

    @classmethod
    @transaction.atomic
    def move_to_vault(cls, *, credential: Credential, vault: Vault) -> Credential:
        """Move one credential between vaults owned by the same user."""
        if credential.vault.user_id != vault.user_id:
            raise VaultOwnershipMismatch(
                "A credential cannot be moved to another user's vault."
            )

        if credential.vault_id == vault.pk:
            return credential

        duplicate_exists = Credential.objects.filter(
            vault_id=vault.pk,
            service_name=credential.service_name,
        ).exclude(pk=credential.pk).exists()
        if duplicate_exists:
            raise DuplicateCredential(
                "A credential with this service name already exists in the target vault."
            )

        credential.vault = vault
        try:
            with transaction.atomic():
                credential.save(update_fields=["vault", "updated_at"])
        except IntegrityError as exc:
            raise DuplicateCredential(
                "A credential with this service name already exists in the target vault."
            ) from exc
        return credential

    @classmethod
    def bulk_move(
        cls,
        *,
        credential_ids: Iterable,
        user_id: int,
        target_vault_id: int,
    ) -> dict:
        """Move all selected credentials or none; never cross user boundaries."""
        ids = cls.normalize_credential_ids(credential_ids)

        with transaction.atomic():
            try:
                target_vault = Vault.objects.select_for_update().get(
                    pk=target_vault_id,
                    user_id=user_id,
                )
            except Vault.DoesNotExist as exc:
                raise VaultOwnershipMismatch(
                    "The destination vault does not belong to this user."
                ) from exc

            credentials = list(
                Credential.objects.select_for_update()
                .filter(pk__in=ids, vault__user_id=user_id)
                .select_related("vault")
                .order_by("pk")
            )
            if len(credentials) != len(ids):
                raise CredentialOwnershipMismatch(
                    "One or more selected credentials do not exist or are not accessible."
                )

            moving = [item for item in credentials if item.vault_id != target_vault.pk]
            unchanged_count = len(credentials) - len(moving)
            if not moving:
                return {
                    "moved_count": 0,
                    "unchanged_count": unchanged_count,
                    "credential_ids": [],
                    "target_vault": target_vault,
                }

            incoming_names = [item.service_name for item in moving]
            incoming_counts = Counter(incoming_names)
            duplicate_names = {
                name for name, count in incoming_counts.items() if count > 1
            }

            existing_names = set(
                Credential.objects.filter(vault_id=target_vault.pk)
                .values_list("service_name", flat=True)
            )
            duplicate_names.update(
                name for name in incoming_names if name in existing_names
            )

            if duplicate_names:
                names = ", ".join(sorted(duplicate_names, key=str.casefold))
                raise DuplicateCredential(
                    f"The destination vault already contains conflicting credential names: {names}."
                )

            moving_ids = [item.pk for item in moving]
            try:
                # A savepoint lets us translate a concurrent unique-constraint
                # collision into a domain error without breaking the outer tx.
                with transaction.atomic():
                    updated_count = Credential.objects.filter(
                        pk__in=moving_ids,
                        vault__user_id=user_id,
                    ).update(
                        vault_id=target_vault.pk,
                        updated_at=timezone.now(),
                    )
                    if updated_count != len(moving_ids):
                        raise CredentialOwnershipMismatch(
                            "The selected credentials changed during the move operation."
                        )
            except IntegrityError as exc:
                raise DuplicateCredential(
                    "A credential name conflicts with an item in the destination vault."
                ) from exc

            return {
                "moved_count": len(moving),
                "unchanged_count": unchanged_count,
                "credential_ids": moving_ids,
                "target_vault": target_vault,
            }

    @classmethod
    def bulk_delete(
        cls,
        *,
        credential_ids: Iterable,
        user,
        master_password: str,
        ip_address: str = "unknown",
    ) -> int:
        """Re-authenticate, then atomically delete selected credentials/history."""
        ids = cls.normalize_credential_ids(credential_ids)
        ReauthenticationService.verify_master_password(
            user=user,
            password=master_password,
            action="credential-bulk-delete",
            ip_address=ip_address,
        )

        return cls._bulk_delete_for_user(
            credential_ids=ids,
            user_id=user.pk,
        )

    @classmethod
    @transaction.atomic
    def _bulk_delete_for_user(cls, *, credential_ids: list[int], user_id: int) -> int:
        credentials = list(
            Credential.objects.select_for_update()
            .filter(pk__in=credential_ids, vault__user_id=user_id)
            .order_by("pk")
        )
        if len(credentials) != len(credential_ids):
            raise CredentialOwnershipMismatch(
                "One or more selected credentials do not exist or are not accessible."
            )

        credential_count = len(credentials)
        if credential_count:
            Credential.objects.filter(
                pk__in=credential_ids,
                vault__user_id=user_id,
            ).delete()
        return credential_count

    @classmethod
    @transaction.atomic
    def delete(cls, credential: Credential) -> int:
        credential_id = credential.pk
        credential.delete()
        return credential_id
