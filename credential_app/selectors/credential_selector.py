from django.db.models import Q
from credential_app.models import Credential
from vault_app.models import Vault


class CredentialSelector:

    @classmethod
    def get_by_id(cls, credential_id: int) -> Credential:
        return Credential.objects.select_related(
            "vault",
            "vault__user",
            "category",
        ).get(pk=credential_id)

    @classmethod
    def get_by_vault(cls, *, vault: Vault):
        return (
            Credential.objects.filter(vault=vault)
            .select_related(
                "category",
            )
        )

    @classmethod
    def get_favorites(cls, vault: Vault):
        return Credential.objects.filter(vault=vault, is_favorite=True)

    @classmethod
    def search(cls, *, vault: Vault, user_id: int, query: str):
        return (
            Credential.objects
            .filter(
                vault__user_id=user_id,
            )
            .filter(
                Q(service_name__icontains=query)
                |
                Q(login_username__icontains=query)
                |
                Q(login_email__icontains=query)
                |
                Q(category__name__icontains=query)
                |
                Q(vault__name__icontains=query)
            )
            .select_related(
                "vault",
                "category",
            )
        )

    @classmethod
    def exists_by_name(cls, *, vault:Vault, service_name:str) -> bool:
        return Credential.objects.filter(
            vault=vault,
            service_name=service_name,
        ).exists()

    @classmethod
    def count(cls, vault:Vault) -> int:
        return Credential.objects.filter(vault=vault).count()

    @classmethod
    def get_recent(cls, vault: Vault):
        return Credential.objects.filter(vault=vault).order_by("-updated_at")



