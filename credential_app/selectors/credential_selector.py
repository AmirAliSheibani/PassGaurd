from django.db.models import Q, QuerySet

from credential_app.models import Credential
from vault_app.models import Vault


class CredentialSelector:
    """Read-only queries for credentials.

    Prefer the user-scoped methods from request-facing code. ``get_by_id`` is
    intentionally unscoped and should only be used where authorization has
    already been established by the caller.
    """

    @classmethod
    def get_by_id(cls, credential_id: int) -> Credential:
        return (
            Credential.objects.select_related("vault", "vault__user", "category")
            .get(pk=credential_id)
        )

    @classmethod
    def get_by_id_for_user(cls, credential_id: int, user_id: int) -> Credential:
        return (
            Credential.objects.select_related("vault", "vault__user", "category")
            .get(pk=credential_id, vault__user_id=user_id)
        )

    @classmethod
    def get_by_vault(cls, *, vault: Vault) -> QuerySet[Credential]:
        return (
            Credential.objects.filter(vault_id=vault.pk)
            .select_related("category")
        )

    @classmethod
    def get_favorites(cls, *, vault: Vault) -> QuerySet[Credential]:
        """Return favorite credentials for a single vault without N+1 category queries."""
        return (
            Credential.objects.filter(vault_id=vault.pk, is_favorite=True)
            .select_related("category")
        )

    @classmethod
    def search(
        cls,
        *,
        vault: Vault,
        user_id: int,
        query: str,
    ) -> QuerySet[Credential]:
        """Search credentials within a particular vault owned by ``user_id``."""
        queryset = (
            Credential.objects.filter(
                vault_id=vault.pk,
                vault__user_id=user_id,
            )
            .select_related("category")
        )
        normalized_query = query.strip()
        if not normalized_query:
            return queryset

        return queryset.filter(
            Q(service_name__icontains=normalized_query)
            | Q(service_url__icontains=normalized_query)
            | Q(login_username__icontains=normalized_query)
            | Q(login_email__icontains=normalized_query)
            | Q(category__name__icontains=normalized_query)
        )

    @classmethod
    def exists_by_name(cls, *, vault: Vault, service_name: str) -> bool:
        """Check names case-insensitively within the supplied vault."""
        return Credential.objects.filter(
            vault_id=vault.pk,
            service_name__iexact=service_name.strip(),
        ).exists()

    @classmethod
    def count(cls, *, vault: Vault) -> int:
        return Credential.objects.filter(vault_id=vault.pk).count()

    @classmethod
    def get_recent(cls, *, vault: Vault) -> QuerySet[Credential]:
        return (
            Credential.objects.filter(vault_id=vault.pk)
            .select_related("category")
            .order_by("-updated_at", "-pk")
        )
