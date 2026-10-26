from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from common.mixins.credentials import CredentialInVaultMixin
from common.mixins.vaults import VaultObjectMixin
from common.security.encryption.encryption_service import EncryptionService
from common.security.encryption.exceptions import EncryptionError

from credential_app.exceptions import DuplicateCredential
from credential_app.forms import (
    CredentialCreateForm,
    CredentialUpdateForm,
    CredentialRotatePasswordForm,
    CredentialMoveToVaultForm,
)
from credential_app.models import Credential
from credential_app.selectors.credential_selector import CredentialSelector
from credential_app.services.credential_service import CredentialService

from vault_app.models import Vault
from vault_app.selectors.vault_selector import VaultSelector


class CredentialListView(LoginRequiredMixin, VaultObjectMixin, TemplateView):
    """Display credentials belonging to the selected vault."""

    template_name = "credential_app/credential_list.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        vault = self.get_vault()
        query = self.request.GET.get("q", "").strip()
        favorites_only = self.request.GET.get("favorites") == "1"

        if query:
            credentials = CredentialSelector.search(vault=vault, user_id=self.request.user.pk, query=query, )
        elif favorites_only:
            credentials = CredentialSelector.get_favorites(vault=vault, )
        else:
            credentials = CredentialSelector.get_by_vault(vault=vault, )

        if query and favorites_only:
            credentials = credentials.filter(is_favorite=True)

        context.update({
            "vault": vault,
            "credentials": credentials,
            "query": query,
            "favorites_only": favorites_only,
            "credential_count": CredentialSelector.count(vault=vault, ),
        })

        return context


class CredentialCreateView(LoginRequiredMixin, VaultObjectMixin, View, ):
    """Create a credential inside a vault owned by the user."""

    template_name = "credential_app/credential_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        vault = self.get_vault()

        form = CredentialCreateForm(user=request.user, vault=vault, )

        return render(request, self.template_name, {"form": form, "vault": vault, }, )

    def post(self, request, *args, **kwargs):
        vault = self.get_vault()

        form = CredentialCreateForm(request.POST, user=request.user, vault=vault, )

        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "vault": vault, }, )

        data = form.cleaned_data.copy()
        data.pop("confirm_password", None)

        try:
            credential = CredentialService.create(vault=vault, data=data, )
        except DuplicateCredential as exc:
            form.add_error("service_name", str(exc))

            return render(request, self.template_name, {"form": form, "vault": vault, }, )

        return redirect("credential_app:detail", username=request.user.username, vault_slug=vault.slug,
                        pk=credential.pk, )


@method_decorator(never_cache, name="dispatch")
class CredentialDetailView(LoginRequiredMixin, CredentialInVaultMixin, TemplateView, ):
    """
    Display credential details.

    The password is decrypted only for this detail response,
    not for the credential list.
    """

    template_name = "credential_app/credential_detail.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        credential = self.get_credential()
        vault = credential.vault

        context.update(
            {"vault": vault, "credential": credential, "decrypted_password": None, "password_unavailable": False, })

        try:
            context["decrypted_password"] = (
                EncryptionService.decrypt(credential.password_ciphertext, )
            )
        except EncryptionError:
            # Do not expose ciphertext or internal encryption details.
            context["password_unavailable"] = True

        return context


class CredentialUpdateView(LoginRequiredMixin, CredentialInVaultMixin, View, ):
    """Update credential metadata without changing its password."""

    template_name = "credential_app/credential_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        credential = self.get_credential()
        vault = credential.vault

        form = CredentialUpdateForm(
            user=request.user,
            vault=vault,
            credential=credential,
            initial={
                "service_name": credential.service_name,
                "service_url": credential.service_url,
                "login_username": credential.login_username,
                "login_email": credential.login_email,
                "category": credential.category_id,
                "notes": credential.notes,
                "is_favorite": credential.is_favorite,
            },
        )

        return render(request, self.template_name, {"form": form, "vault": vault, "credential": credential, }, )

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        vault = credential.vault

        form = CredentialUpdateForm(request.POST, user=request.user, vault=vault, credential=credential, )

        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "vault": vault, "credential": credential, }, )

        try:
            CredentialService.update(credential=credential, data=form.cleaned_data, )
        except DuplicateCredential as exc:
            form.add_error("service_name", str(exc))

            return render(request, self.template_name, {"form": form, "vault": vault, "credential": credential, }, )

        return redirect("credential_app:detail", username=request.user.username, vault_slug=vault.slug,
                        pk=credential.pk, )


class CredentialDeleteView(LoginRequiredMixin, CredentialInVaultMixin, View, ):
    """Confirm and delete a credential. Deletion uses POST only."""

    template_name = "credential_app/credential_confirm_delete.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        credential = self.get_credential()

        return render(request, self.template_name, {"vault": credential.vault, "credential": credential, }, )

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        vault = credential.vault

        CredentialService.delete(credential=credential, )

        return redirect("credential_app:list", username=request.user.username, vault_slug=vault.slug, )


class CredentialRotatePasswordView(LoginRequiredMixin, CredentialInVaultMixin, View, ):
    """Replace a credential password and record its history."""

    template_name = "credential_app/credential_rotate_password.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        credential = self.get_credential()

        form = CredentialRotatePasswordForm()

        return render(request, self.template_name,
                      {"form": form, "vault": credential.vault, "credential": credential, }, )

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        vault = credential.vault

        form = CredentialRotatePasswordForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "vault": vault, "credential": credential, }, )

        CredentialService.rotate_password(credential=credential, new_password=form.cleaned_data["new_password"], )

        return redirect("credential_app:detail", username=request.user.username, vault_slug=vault.slug,
                        pk=credential.pk, )


class CredentialToggleFavoriteView(LoginRequiredMixin, CredentialInVaultMixin, View, ):
    """Toggle a credential's favorite status using POST."""

    login_url = "user_app:login"

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        vault = credential.vault

        CredentialService.toggle_favorite(credential=credential, )

        return redirect("credential_app:list", username=request.user.username, vault_slug=vault.slug, )


class CredentialMoveToVaultView(LoginRequiredMixin, CredentialInVaultMixin, View, ):
    """Move a credential to another vault owned by the same user."""

    template_name = "credential_app/credential_move_to_vault.html"
    login_url = "user_app:login"

    def get_form(self, *, credential, data=None):
        form = CredentialMoveToVaultForm(data=data, user=self.request.user, credential=credential, )

        # ModelChoiceField must only accept vaults owned by this user.
        form.fields["target_vault"].queryset = (
            VaultSelector.get_user_vaults(user_id=self.request.user.pk, ).exclude(pk=credential.vault_id)
        )

        return form

    def get(self, request, *args, **kwargs):
        credential = self.get_credential()
        form = self.get_form(credential=credential)

        return render(request, self.template_name,
                      {"form": form, "vault": credential.vault, "credential": credential, }, )

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        source_vault = credential.vault

        form = self.get_form(credential=credential, data=request.POST, )

        if not form.is_valid():
            return render(request, self.template_name,
                          {"form": form, "vault": source_vault, "credential": credential, }, )

        target_vault = form.cleaned_data["target_vault"]

        try:
            CredentialService.move_to_vault(credential=credential, vault=target_vault, )
        except DuplicateCredential as exc:
            form.add_error("target_vault", str(exc))

            return render(request, self.template_name,
                          {"form": form, "vault": source_vault, "credential": credential, }, )

        return redirect("credential_app:detail", username=request.user.username, vault_slug=target_vault.slug,
                        pk=credential.pk, )

