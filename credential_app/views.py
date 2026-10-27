from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
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
from credential_app.selectors.credential_selector import CredentialSelector
from credential_app.services.credential_service import CredentialService

from vault_app.models import Vault
from vault_app.selectors.vault_selector import VaultSelector


def _vault_list_url(*, user, vault):
    return reverse(
        "credential_app:list",
        kwargs={"username": user.username, "vault_slug": vault.slug},
    )


def _credential_detail_url(*, user, vault, credential):
    return reverse(
        "credential_app:detail",
        kwargs={
            "username": user.username,
            "vault_slug": vault.slug,
            "pk": credential.pk,
        },
    )


def _credential_form_context(*, user, form, vault, credential=None):
    """Keep create/update templates shared while giving each state real context."""
    is_edit = credential is not None
    return {
        "form": form,
        "vault": vault,
        "credential": credential,
        "form_heading": "Edit credential" if is_edit else "Add credential",
        "form_description": (
            f"Update the details saved for {credential.service_name}."
            if is_edit
            else f"Save sign-in details in {vault.name}."
        ),
        "submit_label": "Save changes" if is_edit else "Save credential",
        "cancel_url": (
            _credential_detail_url(user=user, vault=vault, credential=credential)
            if is_edit
            else _vault_list_url(user=user, vault=vault)
        ),
        "allow_password_generation": not is_edit,
    }


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
            credentials = CredentialSelector.search(
                vault=vault,
                user_id=self.request.user.pk,
                query=query,
            )
        elif favorites_only:
            credentials = CredentialSelector.get_favorites(vault=vault)
        else:
            credentials = CredentialSelector.get_by_vault(vault=vault)

        if query and favorites_only:
            credentials = credentials.filter(is_favorite=True)

        list_url = _vault_list_url(user=self.request.user, vault=vault)
        clear_search_url = f"{list_url}?favorites=1" if favorites_only else list_url
        create_url = reverse(
            "credential_app:create",
            kwargs={"username": self.request.user.username, "vault_slug": vault.slug},
        )

        context.update(
            {
                "vault": vault,
                "credentials": credentials,
                "query": query,
                "favorites_only": favorites_only,
                "credential_count": CredentialSelector.count(vault=vault),
                "page_heading": "Favorite credentials" if favorites_only else "Credentials",
                "page_description": (
                    f"Favorite entries saved in {vault.name}."
                    if favorites_only
                    else f"Browse and manage sign-in details saved in {vault.name}."
                ),
                "create_url": create_url,
                "list_url": list_url,
                "clear_search_url": clear_search_url,
            }
        )
        return context


class CredentialCreateView(LoginRequiredMixin, VaultObjectMixin, View):
    """Create a credential inside a vault owned by the user."""

    template_name = "credential_app/credential_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        vault = self.get_vault()
        form = CredentialCreateForm(user=request.user, vault=vault)
        return render(
            request,
            self.template_name,
            _credential_form_context(user=request.user, form=form, vault=vault),
        )

    def post(self, request, *args, **kwargs):
        vault = self.get_vault()
        form = CredentialCreateForm(request.POST, user=request.user, vault=vault)
        context = _credential_form_context(user=request.user, form=form, vault=vault)

        if not form.is_valid():
            return render(request, self.template_name, context)

        data = form.cleaned_data.copy()
        data.pop("confirm_password", None)

        try:
            credential = CredentialService.create(vault=vault, data=data)
        except DuplicateCredential as exc:
            form.add_error("service_name", str(exc))
            return render(request, self.template_name, context)

        return redirect(
            "credential_app:detail",
            username=request.user.username,
            vault_slug=vault.slug,
            pk=credential.pk,
        )


@method_decorator(never_cache, name="dispatch")
class CredentialDetailView(LoginRequiredMixin, CredentialInVaultMixin, TemplateView):
    """Display credential details, decrypting its password for this response only."""

    template_name = "credential_app/credential_detail.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        credential = self.get_credential()
        vault = credential.vault

        context.update(
            {
                "vault": vault,
                "credential": credential,
                "decrypted_password": None,
                "password_unavailable": False,
            }
        )

        try:
            context["decrypted_password"] = EncryptionService.decrypt(
                credential.password_ciphertext,
            )
        except EncryptionError:
            # Do not expose ciphertext or internal encryption details.
            context["password_unavailable"] = True

        return context


class CredentialUpdateView(LoginRequiredMixin, CredentialInVaultMixin, View):
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
        return render(
            request,
            self.template_name,
            _credential_form_context(
                user=request.user,
                form=form,
                vault=vault,
                credential=credential,
            ),
        )

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        vault = credential.vault
        form = CredentialUpdateForm(
            request.POST,
            user=request.user,
            vault=vault,
            credential=credential,
        )
        context = _credential_form_context(
            user=request.user,
            form=form,
            vault=vault,
            credential=credential,
        )

        if not form.is_valid():
            return render(request, self.template_name, context)

        try:
            CredentialService.update(credential=credential, data=form.cleaned_data)
        except DuplicateCredential as exc:
            form.add_error("service_name", str(exc))
            return render(request, self.template_name, context)

        return redirect(
            "credential_app:detail",
            username=request.user.username,
            vault_slug=vault.slug,
            pk=credential.pk,
        )


class CredentialDeleteView(LoginRequiredMixin, CredentialInVaultMixin, View):
    """Confirm and delete a credential. Deletion uses POST only."""

    template_name = "credential_app/credential_confirm_delete.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        credential = self.get_credential()
        return render(
            request,
            self.template_name,
            {"vault": credential.vault, "credential": credential},
        )

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        vault = credential.vault
        CredentialService.delete(credential=credential)
        return redirect(
            "credential_app:list",
            username=request.user.username,
            vault_slug=vault.slug,
        )


class CredentialRotatePasswordView(LoginRequiredMixin, CredentialInVaultMixin, View):
    """Replace a credential password and record its history."""

    template_name = "credential_app/credential_rotate_password.html"
    login_url = "user_app:login"

    def _context(self, *, request, form, credential):
        return {
            "form": form,
            "vault": credential.vault,
            "credential": credential,
            "detail_url": _credential_detail_url(
                user=request.user,
                vault=credential.vault,
                credential=credential,
            ),
        }

    def get(self, request, *args, **kwargs):
        credential = self.get_credential()
        form = CredentialRotatePasswordForm()
        return render(request, self.template_name, self._context(request=request, form=form, credential=credential))

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        form = CredentialRotatePasswordForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._context(request=request, form=form, credential=credential))

        CredentialService.rotate_password(
            credential=credential,
            new_password=form.cleaned_data["new_password"],
        )
        return redirect(
            "credential_app:detail",
            username=request.user.username,
            vault_slug=credential.vault.slug,
            pk=credential.pk,
        )


class CredentialToggleFavoriteView(LoginRequiredMixin, CredentialInVaultMixin, View):
    """Toggle a credential's favorite status using POST."""

    login_url = "user_app:login"

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        vault = credential.vault
        CredentialService.toggle_favorite(credential=credential)
        return redirect(
            "credential_app:list",
            username=request.user.username,
            vault_slug=vault.slug,
        )


class CredentialMoveToVaultView(LoginRequiredMixin, CredentialInVaultMixin, View):
    """Move a credential to another vault owned by the same user."""

    template_name = "credential_app/credential_move_to_vault.html"
    login_url = "user_app:login"

    def get_form(self, *, credential, data=None):
        form = CredentialMoveToVaultForm(
            data=data,
            user=self.request.user,
            credential=credential,
        )
        # ModelChoiceField must only accept vaults owned by this user.
        form.fields["target_vault"].queryset = (
            VaultSelector.get_user_vaults(user_id=self.request.user.pk)
            .exclude(pk=credential.vault_id)
        )
        return form

    def _context(self, *, request, form, credential):
        return {
            "form": form,
            "vault": credential.vault,
            "credential": credential,
            "detail_url": _credential_detail_url(
                user=request.user,
                vault=credential.vault,
                credential=credential,
            ),
        }

    def get(self, request, *args, **kwargs):
        credential = self.get_credential()
        form = self.get_form(credential=credential)
        return render(request, self.template_name, self._context(request=request, form=form, credential=credential))

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        form = self.get_form(credential=credential, data=request.POST)
        context = self._context(request=request, form=form, credential=credential)

        if not form.is_valid():
            return render(request, self.template_name, context)

        target_vault = form.cleaned_data["target_vault"]
        try:
            CredentialService.move_to_vault(credential=credential, vault=target_vault)
        except DuplicateCredential as exc:
            form.add_error("target_vault", str(exc))
            return render(request, self.template_name, context)

        return redirect(
            "credential_app:detail",
            username=request.user.username,
            vault_slug=target_vault.slug,
            pk=credential.pk,
        )
