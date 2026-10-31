from django.db.models import Q, QuerySet

from credential_app.models import Credential
from vault_app.models import Vault


class CredentialSelector:
    """Read-only queries for credentials, always scoped explicitly when possible."""

    @classmethod
    def get_by_id(cls, credential_id: int) -> Credential:
        return Credential.objects.select_related(
            "vault",
            "vault__user",
            "category",
        ).get(pk=credential_id)

    @classmethod
    def get_by_id_for_user(cls, credential_id: int, user_id: int) -> Credential:
        return Credential.objects.select_related(
            "vault",
            "vault__user",
            "category",
        ).get(pk=credential_id, vault__user_id=user_id)

    @classmethod
    def get_by_vault(cls, *, vault: Vault) -> QuerySet[Credential]:
        return Credential.objects.filter(vault_id=vault.pk).select_related(
            "vault",
            "category",
        ).order_by("-updated_at", "-pk")

    @classmethod
    def get_favorites(cls, vault: Vault) -> QuerySet[Credential]:
        return cls.get_by_vault(vault=vault).filter(is_favorite=True)

    @classmethod
    def get_all_for_user(cls, *, user_id: int) -> QuerySet[Credential]:
        """Return every credential owned by a user across all of their vaults."""
        return Credential.objects.filter(
            vault__user_id=user_id,
        ).select_related(
            "vault",
            "category",
        ).order_by("-updated_at", "-pk")

    @classmethod
    def get_selected_for_user(
        cls,
        *,
        credential_ids: list[int] | tuple[int, ...],
        user_id: int,
    ) -> QuerySet[Credential]:
        """Return the selected credentials that are owned by the given user."""
        if not credential_ids:
            return Credential.objects.none()

        return cls.get_all_for_user(user_id=user_id).filter(
            pk__in=credential_ids,
        ).order_by("pk")

    @classmethod
    def search(
        cls,
        *,
        vault: Vault,
        user_id: int,
        query: str,
    ) -> QuerySet[Credential]:
        """Search descriptive credential fields within one owned vault."""
        queryset = Credential.objects.filter(
            vault_id=vault.pk,
            vault__user_id=user_id,
        ).select_related(
            "vault",
            "category",
        )

        query = (query or "").strip()[:100]
        if not query:
            return queryset

        return queryset.filter(
            Q(service_name__icontains=query)
            | Q(service_url__icontains=query)
            | Q(login_username__icontains=query)
            | Q(login_email__icontains=query)
            | Q(category__name__icontains=query)
        )

    @classmethod
    def search_for_user(
        cls,
        *,
        user_id: int,
        query: str,
    ) -> QuerySet[Credential]:
        """Search all of a user's vaults without exposing password material."""
        queryset = cls.get_all_for_user(user_id=user_id)
        query = (query or "").strip()[:100]

        if not query:
            return queryset

        return queryset.filter(
            Q(service_name__icontains=query)
            | Q(service_url__icontains=query)
            | Q(login_username__icontains=query)
            | Q(login_email__icontains=query)
            | Q(category__name__icontains=query)
            | Q(vault__name__icontains=query)
        )

    @classmethod
    def exists_by_name(cls, *, vault: Vault, service_name: str) -> bool:
        return Credential.objects.filter(
            vault_id=vault.pk,
            service_name=service_name,
        ).exists()

    @classmethod
    def count(cls, vault: Vault) -> int:
        return Credential.objects.filter(vault_id=vault.pk).count()

    @classmethod
    def count_for_user(cls, *, user_id: int) -> int:
        return Credential.objects.filter(vault__user_id=user_id).count()

    @classmethod
    def get_recent(cls, vault: Vault) -> QuerySet[Credential]:
        return cls.get_by_vault(vault=vault).order_by("-updated_at")
