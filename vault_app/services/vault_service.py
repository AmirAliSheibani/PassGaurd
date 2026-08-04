from django.db import transaction
from ..models import Vault, Category
from django.shortcuts import get_object_or_404


class VaultService:

    @classmethod
    @transaction.atomic
    def create(cls, *,user_id: int, data: dict) -> Vault:
        """
        Create a new Vault instance
        """
        if Vault.objects.filter(user_id=user_id, name__iexact=data["name"]).exists():
            raise Exception(f'Vault with name {data["name"]} already exists')

        vault = Vault.objects.create(**data)
        return vault

    @classmethod
    @transaction.atomic
    def update(cls, *, user_id: int, data: dict) -> Vault:
        """
        Update an existing Vault instance
        """
        vault = get_object_or_404(Vault, user_id=user_id, pk=data["pk"])

        if Vault.objects.filter(user_id=user_id, name=data["name"]).exclude(pk=vault.pk).exists():
            raise Exception(f'Vault with name {data["name"]} already exists')

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










