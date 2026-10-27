import re
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.text import slugify

from vault_app.exceptions import DuplicateCategoryExceptions, DuplicateVaultExceptions
from vault_app.models import Category, Vault

User = get_user_model()

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _normalize_name(value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError("A name is required.")
    normalized = " ".join(value.split())
    if not normalized:
        raise ValidationError("A name is required.")
    return normalized


class VaultService:
    """Business operations for vaults owned by users."""

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        user,
        name: str,
        description: str = "",
        is_default: bool = False,
    ) -> Vault:
        # Serialize vault creation per owner. This also avoids concurrent slug
        # allocation/default-vault races between requests from the same account.
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        normalized_name = _normalize_name(name).capitalize()
        if Vault.objects.filter(user=locked_user, name__iexact=normalized_name).exists():
            raise DuplicateVaultExceptions(
                f'Vault with name "{normalized_name}" already exists.'
            )

        # The route uses Django's ASCII <slug:...> converter. Names that contain
        # only non-ASCII characters (for example, Persian text) still need a stable
        # valid URL key, so fall back to a short opaque slug rather than rejecting
        # an otherwise valid display name.
        base_slug = slugify(normalized_name) or f"vault-{uuid.uuid4().hex[:8]}"

        slug = base_slug
        counter = 2
        while Vault.objects.filter(user=locked_user, slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        if is_default:
            Vault.objects.filter(user=locked_user, is_default=True).update(is_default=False)

        try:
            with transaction.atomic():
                return Vault.objects.create(
                    user=locked_user,
                    name=normalized_name,
                    slug=slug,
                    description=(description or "").strip(),
                    is_default=is_default,
                )
        except IntegrityError as exc:
            if Vault.objects.filter(user_id=locked_user.pk, name__iexact=normalized_name).exists():
                raise DuplicateVaultExceptions(
                    f'Vault with name "{normalized_name}" already exists.'
                ) from exc
            raise

    @classmethod
    @transaction.atomic
    def update(
        cls,
        *,
        vault: Vault,
        name: str,
        description: str = "",
        is_default: bool = False,
    ) -> Vault:
        locked_user = User.objects.select_for_update().get(pk=vault.user_id)
        locked_vault = Vault.objects.select_for_update().get(
            pk=vault.pk,
            user_id=locked_user.pk,
        )
        normalized_name = _normalize_name(name).capitalize()
        duplicate_exists = (
            Vault.objects.filter(user_id=locked_vault.user_id, name__iexact=normalized_name)
            .exclude(pk=locked_vault.pk)
            .exists()
        )
        if duplicate_exists:
            raise DuplicateVaultExceptions(
                f'Vault with name "{normalized_name}" already exists.'
            )

        if is_default:
            Vault.objects.filter(
                user_id=locked_vault.user_id,
                is_default=True,
            ).exclude(pk=locked_vault.pk).update(is_default=False)

        locked_vault.name = normalized_name
        locked_vault.description = (description or "").strip()
        locked_vault.is_default = is_default
        try:
            with transaction.atomic():
                locked_vault.save(update_fields=["name", "description", "is_default"])
        except IntegrityError as exc:
            if Vault.objects.filter(
                user_id=locked_vault.user_id,
                name__iexact=normalized_name,
            ).exclude(pk=locked_vault.pk).exists():
                raise DuplicateVaultExceptions(
                    f'Vault with name "{normalized_name}" already exists.'
                ) from exc
            raise
        return locked_vault

    @classmethod
    @transaction.atomic
    def delete(cls, *, vault: Vault) -> int:
        User.objects.select_for_update().get(pk=vault.user_id)
        locked_vault = Vault.objects.select_for_update().get(
            pk=vault.pk,
            user_id=vault.user_id,
        )
        vault_id = locked_vault.pk
        locked_vault.delete()
        return vault_id


class CategoryService:
    """Business operations for user-owned credential categories."""

    @staticmethod
    def _normalize_color(color: str) -> str:
        if not isinstance(color, str) or not _HEX_COLOR.fullmatch(color.strip()):
            raise ValidationError("Color must be a valid six-digit HEX code, for example #6B7280.")
        return color.strip().upper()

    @classmethod
    @transaction.atomic
    def create(cls, *, user, name: str, color: str) -> Category:
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        normalized_name = _normalize_name(name)
        if Category.objects.filter(user=locked_user, name__iexact=normalized_name).exists():
            raise DuplicateCategoryExceptions(
                f'Category with name "{normalized_name}" already exists.'
            )

        try:
            with transaction.atomic():
                return Category.objects.create(
                    user=locked_user,
                    name=normalized_name,
                    color=cls._normalize_color(color),
                )
        except IntegrityError as exc:
            if Category.objects.filter(user_id=locked_user.pk, name__iexact=normalized_name).exists():
                raise DuplicateCategoryExceptions(
                    f'Category with name "{normalized_name}" already exists.'
                ) from exc
            raise

    @classmethod
    @transaction.atomic
    def update(cls, *, category: Category, name: str, color: str) -> Category:
        locked_user = User.objects.select_for_update().get(pk=category.user_id)
        locked_category = Category.objects.select_for_update().get(
            pk=category.pk,
            user_id=locked_user.pk,
        )
        normalized_name = _normalize_name(name)
        duplicate_exists = (
            Category.objects.filter(
                user_id=locked_category.user_id,
                name__iexact=normalized_name,
            )
            .exclude(pk=locked_category.pk)
            .exists()
        )
        if duplicate_exists:
            raise DuplicateCategoryExceptions(
                f'Category with name "{normalized_name}" already exists.'
            )

        locked_category.name = normalized_name
        locked_category.color = cls._normalize_color(color)
        try:
            with transaction.atomic():
                locked_category.save(update_fields=["name", "color"])
        except IntegrityError as exc:
            if Category.objects.filter(
                user_id=locked_category.user_id,
                name__iexact=normalized_name,
            ).exclude(pk=locked_category.pk).exists():
                raise DuplicateCategoryExceptions(
                    f'Category with name "{normalized_name}" already exists.'
                ) from exc
            raise
        return locked_category

    @classmethod
    @transaction.atomic
    def delete(cls, *, category: Category) -> int:
        User.objects.select_for_update().get(pk=category.user_id)
        locked_category = Category.objects.select_for_update().get(
            pk=category.pk,
            user_id=category.user_id,
        )
        category_id = locked_category.pk
        locked_category.delete()
        return category_id
