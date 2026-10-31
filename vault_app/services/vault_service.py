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

        if Vault.objects.filter(user=user, name__iexact=normalized_name).exists():
            raise DuplicateVaultExceptions(
                f'Vault with name "{normalized_name}" already exists.'
            )

        # A valid Vault name may be Persian/Arabic or otherwise non-Latin.
        # Use a stable ASCII fallback and let the existing per-user slug
        # collision loop make it unique.
        base_slug = slugify(normalized_name) or "vault"

        if is_default:
            Vault.objects.filter(
                user=user,
                is_default=True,
            ).update(
                is_default=False,
            )

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
    def update(cls, *, vault: Vault, name: str, description: str = "", is_default: bool = False) -> Vault:
        """
        Update an existing Vault instance
        """
        normalized_name = " ".join(name.split())
        normalized_name = normalized_name.capitalize()

        duplicate_exist = (
            Vault.objects.filter(user=vault.user, name__iexact=normalized_name)
            .exclude(pk=vault.pk)
            .exists()
        )
        if duplicate_exist:
            raise DuplicateVaultExceptions(
                f'Vault with name "{normalized_name}" already exists.'
            )

        if is_default:
            Vault.objects.filter(
                user=vault.user,
                is_default=True,
            ).exclude(
                pk=vault.pk,
            ).update(
                is_default=False,
            )

        vault.name = normalized_name
        vault.description = description.strip()
        vault.is_default = is_default
        vault.save(
            update_fields=["name", "description", "is_default"]
        )

        return vault

    @classmethod
    @transaction.atomic
    def delete(cls, *, vault: Vault) -> int:

        vault_id = vault.pk
        vault.delete()
        return vault_id


class CategoryService:

    @classmethod
    @transaction.atomic
    def create(cls, *, user, name: str, color: str) -> Category:
        normalized_name = " ".join(name.split())

        duplicate_exist = (
            Category.objects.filter(user=user, name__iexact=normalized_name)
        ).exists()



        if duplicate_exist:
            raise DuplicateCategoryExceptions(
                f'Category with name "{normalized_name}" already exists.'
            )

        return Category.objects.create(
            user=user,
            name=normalized_name,
            color=color
        )

    @classmethod
    @transaction.atomic
    def update(cls, *, category: Category, name: str, color: str) -> Category:
        normalized_name = " ".join(name.split())

        duplicate_exist = (
            Category.objects.filter(user=category.user, name__iexact=normalized_name)
            .exclude(pk=category.pk)
            .exists()
        )

        if duplicate_exist:
            raise DuplicateCategoryExceptions(
                f'Category with name "{normalized_name}" already exists.'
            )

        category.name = normalized_name
        category.color = color
        category.save(
            update_fields=["name", "color"]
        )

        return category

    @classmethod
    @transaction.atomic
    def delete(cls, *, category: Category) -> int:
        category_id = category.pk
        category.delete()

        return category_id

