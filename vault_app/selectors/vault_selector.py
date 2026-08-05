from vault_app.models import Vault, Category
from django.db.models import QuerySet

class VaultSelector:

    @classmethod
    def get_by_id(cls, *, vault_id: int) -> Vault:
        return Vault.objects.get(pk=vault_id)

    @classmethod
    def get_by_id_for_user(cls, *, vault_id: int, user_id: int) -> Vault:
        return Vault.objects.get(pk=vault_id, user_id=user_id)

    @classmethod
    def get_by_default(cls, *, user_id: int) :
        return Vault.objects.get(pk=user_id, is_default=True)

    @classmethod
    def get_user_vaults(cls, *, user_id: int) -> QuerySet[Vault]:
        return Vault.objects.filter(user_id=user_id).order_by("-created_at")

    @classmethod
    def exists_by_name(cls, *, vault_name: int, user_id: int) -> bool:
        return Vault.objects.filter(name__iexact=vault_name, user_id=user_id).exists()

    @classmethod
    def count(cls, *, user_id: int) -> int:
        return Vault.objects.filter(user_id=user_id).count()

    @classmethod
    def get_recent(cls, *, user_id: int) -> Vault:
        return Vault.objects.filter(user_id=user_id).order_by('-created_at').first()


class CategorySelector:

    @classmethod
    def get_by_id(cls, *, category_id: int) -> Category:
        return Category.objects.get(pk=category_id)

    @classmethod
    def get_by_id_for_user(cls, *, category_id: int, user_id: int) -> Category:
        return Category.objects.get(pk=category_id, user_id=user_id)

    @classmethod
    def get_user_categories(cls, *, user_id: int) -> QuerySet[Category]:
        return Category.objects.filter(user_id=user_id).order_by("name")

    @classmethod
    def exists_by_name(cls, *, category_name: int, user_id: int) -> bool:
        return Category.objects.filter(name__iexact=category_name, user_id=user_id).exists()

    @classmethod
    def count(cls, *, user_id: int) -> int:
        return Category.objects.filter(user_id=user_id).count()

    @classmethod
    def get_recent(cls, *, user_id: int) -> Category:
        return Category.objects.filter(user_id=user_id).order_by('-created_at').first()

