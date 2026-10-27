from django.db import IntegrityError, transaction

from common.security.encryption.encryption_service import EncryptionService
from credential_app.exceptions import (
    CategoryOwnershipMismatch,
    DuplicateCredential,
    VaultOwnershipMismatch,
)
from credential_app.models import Credential, CredentialHistory
from vault_app.models import Category, Vault


class CredentialService:
    """Business operations for credential records.

    Input dictionaries are deliberately allow-listed. This avoids passing form-only
    values (such as confirmation fields) or unexpected fields into Model.objects.create.
    Authorization still belongs to the view/mixin; these methods enforce domain
    invariants such as category ownership and duplicate service names.
    """

    CREATE_FIELDS = frozenset(
        {
            "service_name",
            "service_url",
            "login_username",
            "login_email",
            "category",
            "is_favorite",
            "notes",
        }
    )
    UPDATE_FIELDS = CREATE_FIELDS

    @staticmethod
    def _validate_category_owner(*, category: Category | None, user_id: int) -> None:
        if category is not None and category.user_id != user_id:
            raise CategoryOwnershipMismatch(
                "A credential can only use a category owned by the vault's user."
            )

    @staticmethod
    def _ensure_unique_name(*, vault_id: int, service_name: str, exclude_id: int | None = None) -> None:
        queryset = Credential.objects.filter(
            vault_id=vault_id,
            service_name__iexact=service_name.strip(),
        )
        if exclude_id is not None:
            queryset = queryset.exclude(pk=exclude_id)
        if queryset.exists():
            raise DuplicateCredential(
                "A credential with this service name already exists in the vault."
            )

    @classmethod
    @transaction.atomic
    def create(cls, *, vault: Vault, data: dict) -> Credential:
        """Create a credential after encrypting its plaintext password."""
        plaintext_password = data.get("password")
        if not isinstance(plaintext_password, str) or not plaintext_password:
            raise ValueError("A non-empty plaintext password is required to create a credential.")

        locked_vault = Vault.objects.select_for_update().get(pk=vault.pk)
        payload = {key: data[key] for key in cls.CREATE_FIELDS if key in data}
        service_name = payload.get("service_name")
        if not isinstance(service_name, str) or not service_name.strip():
            raise ValueError("A service name is required to create a credential.")
        payload["service_name"] = service_name.strip()

        cls._validate_category_owner(
            category=payload.get("category"),
            user_id=locked_vault.user_id,
        )
        cls._ensure_unique_name(
            vault_id=locked_vault.pk,
            service_name=payload["service_name"],
        )
        payload["password_ciphertext"] = EncryptionService.encrypt(plaintext_password)
        try:
            with transaction.atomic():
                return Credential.objects.create(vault=locked_vault, **payload)
        except IntegrityError as exc:
            # Handles a duplicate inserted after the preflight query by a concurrent request.
            if Credential.objects.filter(
                vault_id=locked_vault.pk,
                service_name__iexact=payload["service_name"],
            ).exists():
                raise DuplicateCredential(
                    "A credential with this service name already exists in the vault."
                ) from exc
            raise

    @classmethod
    @transaction.atomic
    def update(cls, *, credential: Credential, data: dict) -> Credential:
        """Update credential metadata without allowing password changes here."""
        locked_credential = (
            Credential.objects.select_for_update()
            .select_related("vault")
            .get(pk=credential.pk)
        )
        payload = {key: data[key] for key in cls.UPDATE_FIELDS if key in data}

        if "service_name" in payload:
            service_name = payload["service_name"]
            if not isinstance(service_name, str) or not service_name.strip():
                raise ValueError("A service name cannot be empty.")
            payload["service_name"] = service_name.strip()
            cls._ensure_unique_name(
                vault_id=locked_credential.vault_id,
                service_name=payload["service_name"],
                exclude_id=locked_credential.pk,
            )

        if "category" in payload:
            cls._validate_category_owner(
                category=payload["category"],
                user_id=locked_credential.vault.user_id,
            )

        for field, value in payload.items():
            setattr(locked_credential, field, value)

        try:
            with transaction.atomic():
                locked_credential.save(update_fields=[*payload.keys(), "updated_at"])
        except IntegrityError as exc:
            if "service_name" in payload and Credential.objects.filter(
                vault_id=locked_credential.vault_id,
                service_name__iexact=payload["service_name"],
            ).exclude(pk=locked_credential.pk).exists():
                raise DuplicateCredential(
                    "A credential with this service name already exists in the vault."
                ) from exc
            raise
        return locked_credential

    @classmethod
    @transaction.atomic
    def rotate_password(cls, *, credential: Credential, new_password: str) -> Credential:
        """Encrypt a replacement password and save a ciphertext-only history record."""
        if not isinstance(new_password, str) or not new_password:
            raise ValueError("A non-empty new password is required.")

        locked_credential = Credential.objects.select_for_update().get(pk=credential.pk)
        old_ciphertext = locked_credential.password_ciphertext
        new_ciphertext = EncryptionService.encrypt(new_password)

        locked_credential.password_ciphertext = new_ciphertext
        locked_credential.save(update_fields=["password_ciphertext", "updated_at"])
        CredentialHistory.objects.create(
            credential=locked_credential,
            old_password_ciphertext=old_ciphertext,
            new_password_ciphertext=new_ciphertext,
        )
        return locked_credential

    @classmethod
    @transaction.atomic
    def toggle_favorite(cls, *, credential: Credential) -> Credential:
        """Toggle favorite state from the freshly locked database value."""
        locked_credential = Credential.objects.select_for_update().get(pk=credential.pk)
        locked_credential.is_favorite = not locked_credential.is_favorite
        locked_credential.save(update_fields=["is_favorite", "updated_at"])
        return locked_credential

    @classmethod
    @transaction.atomic
    def move_to_vault(cls, *, credential: Credential, vault: Vault) -> Credential:
        """Move a credential between vaults belonging to the same user."""
        locked_credential = (
            Credential.objects.select_for_update()
            .select_related("vault")
            .get(pk=credential.pk)
        )
        target_vault = Vault.objects.select_for_update().get(pk=vault.pk)

        if locked_credential.vault.user_id != target_vault.user_id:
            raise VaultOwnershipMismatch(
                "A credential cannot be moved to another user's vault."
            )

        if locked_credential.vault_id == target_vault.pk:
            return locked_credential

        duplicate_exists = Credential.objects.filter(
            vault_id=target_vault.pk,
            service_name__iexact=locked_credential.service_name,
        ).exclude(pk=locked_credential.pk).exists()
        if duplicate_exists:
            raise DuplicateCredential(
                "A credential with this service name already exists in the target vault."
            )

        locked_credential.vault = target_vault
        try:
            with transaction.atomic():
                locked_credential.save(update_fields=["vault", "updated_at"])
        except IntegrityError as exc:
            duplicate_exists = Credential.objects.filter(
                vault_id=target_vault.pk,
                service_name__iexact=locked_credential.service_name,
            ).exclude(pk=locked_credential.pk).exists()
            if duplicate_exists:
                raise DuplicateCredential(
                    "A credential with this service name already exists in the target vault."
                ) from exc
            raise
        return locked_credential

    @classmethod
    @transaction.atomic
    def delete(cls, *, credential: Credential) -> int:
        """Delete a credential; related password-history rows cascade with it."""
        locked_credential = Credential.objects.select_for_update().get(pk=credential.pk)
        credential_id = locked_credential.pk
        locked_credential.delete()
        return credential_id
