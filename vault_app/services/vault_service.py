from django.db import transaction
from vault_app.models import Vault, Category
from django.shortcuts import get_object_or_404
from vault_app.exceptions import DuplicateVaultExceptions, DuplicateCategoryExceptions
from django.utils.text import slugify

class VaultService:

    @classmethod
    @transaction.atomic
    def create(cls, *, user, name: str, description: str = "", is_default: bool = False) -> Vault:
        normalized_name = " ".join(name.split())
        normalized_name = normalized_name.capitalize()

        base_slug = slugify(normalized_name)

        slug = base_slug
        counter = 2

        while Vault.objects.filter(user=user, slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return Vault.objects.create(
            user=user,
            name=normalized_name,
            slug=slug,
            description=description.strip(),
            is_default=is_default,
        )

    @classmethod
    @transaction.atomic
    def update(cls, *, user_id: int, data: dict) -> Vault:
        """
        Update an existing Vault instance
        """
        vault = get_object_or_404(Vault, user_id=user_id, pk=data["pk"])

        if Vault.objects.filter(user_id=user_id, name__iexact=data["name"]).exclude(pk=vault.pk).exists():
            raise DuplicateVaultExceptions(f'Vault with name {data["name"]} already exists')

        vault.name = data["name"]
        vault.description = data["description"]
        vault.save(update_fields=["name", "description"])
        return vault

    @classmethod
    @transaction.atomic
    def delete(cls, *, user_id: int, data: dict) -> int:
        vault = get_object_or_404(Vault, user_id=user_id, pk=data["pk"])

        vault_id = vault.pk
        vault.delete()
        return vault_id


class CategoryService:
    @classmethod
    @transaction.atomic
    def create(cls, *, user_id: int, data: dict) -> Category:
        if Category.objects.filter(user_id=user_id, name__iexact=data["name"]).exists():
            raise DuplicateCategoryExceptions(f'Category with name {data["name"]} already exists')

        category = Category.objects.create(user_id=user_id, **data)
        return category

    @classmethod
    @transaction.atomic
    def update(cls, *, user_id: int, data: dict) -> Category:
        category = get_object_or_404(Category, user_id=user_id, pk=data["pk"])

        if Category.objects.filter(user_id=user_id, name__iexact=data["name"]).exclude(pk=category.pk).exists():
            raise DuplicateCategoryExceptions(f'Category with name "{data["name"]}" already exists.')

        category.name = data["name"]
        category.color = data["color"]

        category.save(update_fields=["name", "color"])

        return category

    @classmethod
    @transaction.atomic
    def delete(cls, *, user_id: int, data: dict) -> int:
        category = get_object_or_404(Category, user_id=user_id, pk=data["pk"])

        category_id = category.pk
        category.delete()
        return category_id

