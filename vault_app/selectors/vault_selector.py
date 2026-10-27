from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from vault_app.models import Category, Vault

User = get_user_model()


class VaultSelector:
    """Read-only queries for vaults. Use user-scoped methods in request paths."""

    @classmethod
    def get_by_id(cls, *, vault_id: int) -> Vault:
        """Unscoped lookup for callers that have already authorized access."""
        return Vault.objects.select_related("user").get(pk=vault_id)

    @classmethod
    def get_by_id_for_user(cls, *, vault_id: int, user_id: int) -> Vault:
        return Vault.objects.select_related("user").get(pk=vault_id, user_id=user_id)

    @classmethod
    def get_by_username_and_slug_for_user(
        cls,
        *,
        username: str,
        vault_slug: str,
        user: User,
    ) -> Vault:
        return Vault.objects.select_related("user").get(
            user_id=user.pk,
            user__username__iexact=username,
            slug=vault_slug,
        )

    @classmethod
    def get_by_default(cls, *, user_id: int) -> Vault:
        return Vault.objects.get(user_id=user_id, is_default=True)

    @classmethod
    def get_user_vaults(cls, *, user_id: int) -> QuerySet[Vault]:
        return Vault.objects.filter(user_id=user_id).order_by("-is_default", "name", "pk")

    @classmethod
    def exists_by_name(cls, *, vault_name: str, user_id: int) -> bool:
        return Vault.objects.filter(
            name__iexact=vault_name.strip(),
            user_id=user_id,
        ).exists()

    @classmethod
    def count(cls, *, user_id: int) -> int:
        return Vault.objects.filter(user_id=user_id).count()

    @classmethod
    def get_recent(cls, *, user_id: int) -> Vault | None:
        return (
            Vault.objects.filter(user_id=user_id)
            .order_by("-created_at", "-pk")
            .first()
        )


class CategorySelector:
    """Read-only queries for user-owned categories."""

    @classmethod
    def get_by_id(cls, *, category_id: int) -> Category:
        """Unscoped lookup; use ``get_by_id_for_user`` for request-facing code."""
        return Category.objects.select_related("user").get(pk=category_id)

    @classmethod
    def get_by_id_for_user(cls, *, category_id: int, user_id: int) -> Category:
        return Category.objects.get(pk=category_id, user_id=user_id)

    @classmethod
    def get_user_categories(cls, *, user_id: int) -> QuerySet[Category]:
        return Category.objects.filter(user_id=user_id).order_by("name", "pk")

    @classmethod
    def exists_by_name(cls, *, category_name: str, user_id: int) -> bool:
        return Category.objects.filter(
            name__iexact=category_name.strip(),
            user_id=user_id,
        ).exists()

    @classmethod
    def count(cls, *, user_id: int) -> int:
        return Category.objects.filter(user_id=user_id).count()

    @classmethod
    def get_recent(cls, *, user_id: int) -> Category | None:
        return (
            Category.objects.filter(user_id=user_id)
            .order_by("-created_at", "-pk")
            .first()
        )
