from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from common.mixins.credentials import CredentialInVaultMixin
from common.mixins.vaults import VaultObjectMixin
from common.security.encryption.encryption_service import EncryptionService
from common.security.encryption.exceptions import EncryptionError
from common.security.reauthentication import InvalidMasterPassword
from common.security.rate_limit.exceptions import RateLimitExceeded
from credential_app.exceptions import (
    CredentialOwnershipMismatch,
    DuplicateCredential,
    InvalidCredentialSelection,
    VaultOwnershipMismatch,
)
from credential_app.forms import (
    BulkCredentialDeleteConfirmationForm,
    BulkCredentialMoveForm,
    CredentialCreateForm,
    CredentialMoveToVaultForm,
    CredentialRotatePasswordForm,
    CredentialUpdateForm,
)
from credential_app.selectors.credential_selector import CredentialSelector
from credential_app.services.credential_service import CredentialService
from vault_app.selectors.vault_selector import VaultSelector


CREDENTIALS_PER_PAGE = 50
BULK_DELETE_SELECTION_SALT = "credential_app.bulk_delete_selection"
BULK_DELETE_SELECTION_MAX_AGE = 300


def _paginate(queryset, request):
    paginator = Paginator(queryset, CREDENTIALS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    return paginator, page_obj


def _safe_return_to(request):
    candidate = request.POST.get("return_to", "")
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse("credential_app:global_list")


def _selected_ids_from_request(request) -> list[int]:
    return CredentialService.normalize_credential_ids(
        request.POST.getlist("credential_ids")
    )


def _get_selected_credentials_or_404(*, credential_ids: list[int], user_id: int):
    credentials = list(
        CredentialSelector.get_selected_for_user(
            credential_ids=credential_ids,
            user_id=user_id,
        )
    )
    if len(credentials) != len(credential_ids):
        raise Http404
    return credentials


def _sign_bulk_delete_selection(*, credential_ids: list[int], user_id: int) -> str:
    """Bind the review step to the exact IDs and owner that were displayed."""
    return signing.dumps(
        {"user_id": int(user_id), "credential_ids": credential_ids},
        salt=BULK_DELETE_SELECTION_SALT,
    )


def _load_bulk_delete_selection(*, token: str, user_id: int) -> list[int]:
    """Load a short-lived, tamper-evident selection token for confirmation."""
    try:
        payload = signing.loads(
            token,
            salt=BULK_DELETE_SELECTION_SALT,
            max_age=BULK_DELETE_SELECTION_MAX_AGE,
        )
    except signing.BadSignature as exc:
        raise InvalidCredentialSelection(
            "The deletion review expired or is invalid. Please select the credentials again."
        ) from exc

    if not isinstance(payload, dict) or payload.get("user_id") != int(user_id):
        raise InvalidCredentialSelection(
            "The deletion review does not belong to this account."
        )

    try:
        return CredentialService.normalize_credential_ids(payload.get("credential_ids"))
    except InvalidCredentialSelection as exc:
        raise InvalidCredentialSelection(
            "The deletion review is invalid. Please select the credentials again."
        ) from exc


@method_decorator(never_cache, name="dispatch")
class CredentialListView(LoginRequiredMixin, VaultObjectMixin, TemplateView):
    """Display and search credentials inside the selected vault."""

    template_name = "credential_app/credential_list.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vault = self.get_vault()
        query = self.request.GET.get("q", "").strip()[:100]
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

        paginator, page_obj = _paginate(credentials, self.request)
        list_url = reverse(
            "credential_app:list",
            kwargs={"username": self.request.user.username, "vault_slug": vault.slug},
        )

        context.update({
            "vault": vault,
            "credentials": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "query": query,
            "favorites_only": favorites_only,
            "credential_count": CredentialSelector.count(vault=vault),
            "result_count": paginator.count,
            "target_vaults": VaultSelector.get_user_vaults(user_id=self.request.user.pk),
            "page_heading": "Favorite credentials" if favorites_only else f"{vault.name} credentials",
            "page_description": (
                "Your favorite credentials in this vault."
                if favorites_only else "Search and manage the credentials stored in this vault."
            ),
            "create_url": reverse(
                "credential_app:create",
                kwargs={"username": self.request.user.username, "vault_slug": vault.slug},
            ),
            "list_url": list_url,
            "search_url": list_url,
            "clear_search_url": list_url + ("?favorites=1" if favorites_only else ""),
            "bulk_move_url": reverse("credential_app:bulk_move"),
            "bulk_delete_url": reverse("credential_app:bulk_delete"),
            "show_vault_column": False,
            "return_to": self.request.get_full_path(),
        })
        return context


@method_decorator(never_cache, name="dispatch")
class GlobalCredentialListView(LoginRequiredMixin, TemplateView):
    """Search and manage all credentials across the current user's vaults."""

    template_name = "credential_app/global_credential_list.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()[:100]
        favorites_only = self.request.GET.get("favorites") == "1"

        credentials = CredentialSelector.search_for_user(
            user_id=self.request.user.pk,
            query=query,
        )
        if favorites_only:
            credentials = credentials.filter(is_favorite=True)

        paginator, page_obj = _paginate(credentials, self.request)
        vaults = VaultSelector.get_user_vaults(user_id=self.request.user.pk)
        first_vault = vaults.first()
        create_url = (
            reverse(
                "credential_app:create",
                kwargs={
                    "username": self.request.user.username,
                    "vault_slug": first_vault.slug,
                },
            )
            if first_vault else reverse("vault_app:create")
        )

        context.update({
            "credentials": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "query": query,
            "favorites_only": favorites_only,
            "credential_count": CredentialSelector.count_for_user(
                user_id=self.request.user.pk,
            ),
            "result_count": paginator.count,
            "target_vaults": vaults,
            "page_heading": "All credentials",
            "page_description": "Search across every vault in your PassGuard workspace.",
            "create_url": create_url,
            "list_url": reverse("credential_app:global_list"),
            "search_url": reverse("credential_app:global_list"),
            "clear_search_url": reverse("credential_app:global_list")
            + ("?favorites=1" if favorites_only else ""),
            "bulk_move_url": reverse("credential_app:bulk_move"),
            "bulk_delete_url": reverse("credential_app:bulk_delete"),
            "show_vault_column": True,
            "return_to": self.request.get_full_path(),
            "vault": None,
        })
        return context


class BulkCredentialMoveView(LoginRequiredMixin, View):
    """Move a selected set of owned credentials to one of the user's vaults."""

    login_url = "user_app:login"

    def post(self, request, *args, **kwargs):
        return_to = _safe_return_to(request)
        try:
            credential_ids = _selected_ids_from_request(request)
        except InvalidCredentialSelection as exc:
            messages.error(request, str(exc))
            return redirect(return_to)

        form = BulkCredentialMoveForm(request.POST, user=request.user)
        if not form.is_valid():
            messages.error(request, "Choose a valid destination vault before moving credentials.")
            return redirect(return_to)

        target_vault = form.cleaned_data["target_vault"]
        try:
            result = CredentialService.bulk_move(
                credential_ids=credential_ids,
                user_id=request.user.pk,
                target_vault_id=target_vault.pk,
            )
        except (CredentialOwnershipMismatch, VaultOwnershipMismatch) as exc:
            raise Http404 from exc
        except DuplicateCredential as exc:
            messages.error(request, str(exc))
            return redirect(return_to)
        except InvalidCredentialSelection as exc:
            messages.error(request, str(exc))
            return redirect(return_to)

        moved_count = result["moved_count"]
        unchanged_count = result["unchanged_count"]
        if moved_count:
            messages.success(
                request,
                f"{moved_count} credential(s) moved to {target_vault.name}."
                + (f" {unchanged_count} already belonged to that vault." if unchanged_count else ""),
            )
        else:
            messages.info(request, "All selected credentials were already in that vault.")
        return redirect(return_to)


@method_decorator(never_cache, name="dispatch")
class BulkCredentialDeleteView(LoginRequiredMixin, View):
    """Two-step bulk deletion: review selection, then verify master password."""

    login_url = "user_app:login"
    template_name = "credential_app/bulk_delete_confirm.html"

    def post(self, request, *args, **kwargs):
        return_to = _safe_return_to(request)

        if request.POST.get("stage") == "confirm":
            try:
                credential_ids = _load_bulk_delete_selection(
                    token=request.POST.get("selection_token", ""),
                    user_id=request.user.pk,
                )
                selected_credentials = _get_selected_credentials_or_404(
                    credential_ids=credential_ids,
                    user_id=request.user.pk,
                )
            except (InvalidCredentialSelection, Http404) as exc:
                messages.error(
                    request,
                    "The deletion review expired or changed. Select the credentials again.",
                )
                return redirect(return_to)
        else:
            try:
                credential_ids = _selected_ids_from_request(request)
                selected_credentials = _get_selected_credentials_or_404(
                    credential_ids=credential_ids,
                    user_id=request.user.pk,
                )
            except InvalidCredentialSelection as exc:
                messages.error(request, str(exc))
                return redirect(return_to)
            except Http404:
                raise

            selection_token = _sign_bulk_delete_selection(
                credential_ids=credential_ids,
                user_id=request.user.pk,
            )
            form = BulkCredentialDeleteConfirmationForm()
            return render(request, self.template_name, {
                "form": form,
                "selected_credentials": selected_credentials,
                "credential_ids": credential_ids,
                "selection_token": selection_token,
                "return_to": return_to,
            })

        selection_token = request.POST.get("selection_token", "")
        form = BulkCredentialDeleteConfirmationForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form,
                "selected_credentials": selected_credentials,
                "credential_ids": credential_ids,
                "selection_token": selection_token,
                "return_to": return_to,
            })

        try:
            deleted_count = CredentialService.bulk_delete(
                credential_ids=credential_ids,
                user=request.user,
                master_password=form.cleaned_data["master_password"],
                ip_address=request.META.get("REMOTE_ADDR", "unknown"),
            )
        except InvalidMasterPassword:
            form.add_error("master_password", "The master password is incorrect.")
            return render(request, self.template_name, {
                "form": form,
                "selected_credentials": selected_credentials,
                "credential_ids": credential_ids,
                "selection_token": selection_token,
                "return_to": return_to,
            }, status=400)
        except RateLimitExceeded:
            form.add_error(None, "Too many confirmation attempts. Please try again later.")
            return render(request, self.template_name, {
                "form": form,
                "selected_credentials": selected_credentials,
                "credential_ids": credential_ids,
                "selection_token": selection_token,
                "return_to": return_to,
            }, status=429)
        except CredentialOwnershipMismatch as exc:
            raise Http404 from exc

        messages.success(
            request,
            f"{deleted_count} credential(s) and their password history were permanently deleted.",
        )
        return redirect(return_to)

@method_decorator(never_cache, name="dispatch")
class CredentialCreateView(LoginRequiredMixin, VaultObjectMixin, View):
    """Create a credential inside a vault owned by the user."""

    template_name = "credential_app/credential_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        vault = self.get_vault()
        form = CredentialCreateForm(user=request.user, vault=vault)
        return render(request, self.template_name, {
            "form": form,
            "vault": vault,
            "form_heading": "Add credential",
            "form_description": f"Save a new sign-in entry in {vault.name}.",
            "cancel_url": reverse(
                "credential_app:list",
                kwargs={"username": request.user.username, "vault_slug": vault.slug},
            ),
            "submit_label": "Save credential",
            "allow_password_generation": True,
        })

    def post(self, request, *args, **kwargs):
        vault = self.get_vault()
        form = CredentialCreateForm(request.POST, user=request.user, vault=vault)
        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form,
                "vault": vault,
                "form_heading": "Add credential",
                "form_description": f"Save a new sign-in entry in {vault.name}.",
                "cancel_url": reverse(
                    "credential_app:list",
                    kwargs={"username": request.user.username, "vault_slug": vault.slug},
                ),
                "submit_label": "Save credential",
                "allow_password_generation": True,
            })

        data = form.cleaned_data.copy()
        data.pop("confirm_password", None)
        try:
            credential = CredentialService.create(vault=vault, data=data)
        except DuplicateCredential as exc:
            form.add_error("service_name", str(exc))
            return render(request, self.template_name, {
                "form": form,
                "vault": vault,
                "form_heading": "Add credential",
                "form_description": f"Save a new sign-in entry in {vault.name}.",
                "cancel_url": reverse(
                    "credential_app:list",
                    kwargs={"username": request.user.username, "vault_slug": vault.slug},
                ),
                "submit_label": "Save credential",
                "allow_password_generation": True,
            })

        return redirect(
            "credential_app:detail",
            username=request.user.username,
            vault_slug=vault.slug,
            pk=credential.pk,
        )


@method_decorator(never_cache, name="dispatch")
class CredentialDetailView(LoginRequiredMixin, CredentialInVaultMixin, TemplateView):
    """Display metadata only; password plaintext is fetched after explicit reveal."""

    template_name = "credential_app/credential_detail.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        credential = self.get_credential()
        context.update({
            "vault": credential.vault,
            "credential": credential,
            "password_reveal_url": reverse(
                "credential_app:reveal_password",
                kwargs={
                    "username": self.request.user.username,
                    "vault_slug": credential.vault.slug,
                    "pk": credential.pk,
                },
            ),
        })
        return context


@method_decorator(never_cache, name="dispatch")
class CredentialRevealPasswordView(LoginRequiredMixin, CredentialInVaultMixin, View):
    """Return a credential password only after an explicit same-origin POST."""

    login_url = "user_app:login"

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        try:
            password = EncryptionService.decrypt(credential.password_ciphertext)
        except EncryptionError:
            return JsonResponse(
                {"error": "The stored password cannot currently be decrypted."},
                status=503,
            )

        response = JsonResponse({"password": password})
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        return response


@method_decorator(never_cache, name="dispatch")
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
        return render(request, self.template_name, {
            "form": form,
            "vault": vault,
            "credential": credential,
            "form_heading": f"Edit {credential.service_name}",
            "form_description": "Update the saved account details without changing its password.",
            "cancel_url": reverse(
                "credential_app:detail",
                kwargs={"username": request.user.username, "vault_slug": vault.slug, "pk": credential.pk},
            ),
            "submit_label": "Save changes",
            "allow_password_generation": False,
        })

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        vault = credential.vault
        form = CredentialUpdateForm(
            request.POST,
            user=request.user,
            vault=vault,
            credential=credential,
        )
        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form,
                "vault": vault,
                "credential": credential,
                "form_heading": f"Edit {credential.service_name}",
                "form_description": "Update the saved account details without changing its password.",
                "cancel_url": reverse(
                    "credential_app:detail",
                    kwargs={"username": request.user.username, "vault_slug": vault.slug, "pk": credential.pk},
                ),
                "submit_label": "Save changes",
                "allow_password_generation": False,
            })
        try:
            CredentialService.update(credential=credential, data=form.cleaned_data)
        except DuplicateCredential as exc:
            form.add_error("service_name", str(exc))
            return render(request, self.template_name, {
                "form": form,
                "vault": vault,
                "credential": credential,
                "form_heading": f"Edit {credential.service_name}",
                "form_description": "Update the saved account details without changing its password.",
                "cancel_url": reverse(
                    "credential_app:detail",
                    kwargs={"username": request.user.username, "vault_slug": vault.slug, "pk": credential.pk},
                ),
                "submit_label": "Save changes",
                "allow_password_generation": False,
            })
        return redirect(
            "credential_app:detail",
            username=request.user.username,
            vault_slug=vault.slug,
            pk=credential.pk,
        )


@method_decorator(never_cache, name="dispatch")
class CredentialDeleteView(LoginRequiredMixin, CredentialInVaultMixin, View):
    """Confirm and delete a single credential. Deletion uses POST only."""

    template_name = "credential_app/credential_confirm_delete.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        credential = self.get_credential()
        return render(request, self.template_name, {
            "vault": credential.vault,
            "credential": credential,
        })

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        vault = credential.vault
        CredentialService.delete(credential=credential)
        return redirect(
            "credential_app:list",
            username=request.user.username,
            vault_slug=vault.slug,
        )


@method_decorator(never_cache, name="dispatch")
class CredentialRotatePasswordView(LoginRequiredMixin, CredentialInVaultMixin, View):
    """Replace a credential password and record its history."""

    template_name = "credential_app/credential_rotate_password.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        credential = self.get_credential()
        detail_url = reverse(
            "credential_app:detail",
            kwargs={
                "username": request.user.username,
                "vault_slug": credential.vault.slug,
                "pk": credential.pk,
            },
        )
        return render(request, self.template_name, {
            "form": CredentialRotatePasswordForm(),
            "vault": credential.vault,
            "credential": credential,
            "detail_url": detail_url,
        })

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        vault = credential.vault
        detail_url = reverse(
            "credential_app:detail",
            kwargs={
                "username": request.user.username,
                "vault_slug": vault.slug,
                "pk": credential.pk,
            },
        )
        form = CredentialRotatePasswordForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form,
                "vault": vault,
                "credential": credential,
                "detail_url": detail_url,
            })

        CredentialService.rotate_password(
            credential=credential,
            new_password=form.cleaned_data["new_password"],
        )
        return redirect(
            "credential_app:detail",
            username=request.user.username,
            vault_slug=vault.slug,
            pk=credential.pk,
        )


class CredentialToggleFavoriteView(LoginRequiredMixin, CredentialInVaultMixin, View):
    """Toggle favorite status using POST."""

    login_url = "user_app:login"

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        CredentialService.toggle_favorite(credential=credential)
        return redirect(_safe_return_to(request))


@method_decorator(never_cache, name="dispatch")
class CredentialMoveToVaultView(LoginRequiredMixin, CredentialInVaultMixin, View):
    """Move one credential to another vault owned by the same user."""

    template_name = "credential_app/credential_move_to_vault.html"
    login_url = "user_app:login"

    def get_form(self, *, credential, data=None):
        return CredentialMoveToVaultForm(
            data=data,
            user=self.request.user,
            credential=credential,
        )

    def get(self, request, *args, **kwargs):
        credential = self.get_credential()
        form = self.get_form(credential=credential)
        detail_url = reverse(
            "credential_app:detail",
            kwargs={
                "username": request.user.username,
                "vault_slug": credential.vault.slug,
                "pk": credential.pk,
            },
        )
        return render(request, self.template_name, {
            "form": form,
            "vault": credential.vault,
            "credential": credential,
            "detail_url": detail_url,
        })

    def post(self, request, *args, **kwargs):
        credential = self.get_credential()
        source_vault = credential.vault
        detail_url = reverse(
            "credential_app:detail",
            kwargs={
                "username": request.user.username,
                "vault_slug": source_vault.slug,
                "pk": credential.pk,
            },
        )
        form = self.get_form(credential=credential, data=request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form,
                "vault": source_vault,
                "credential": credential,
                "detail_url": detail_url,
            })

        target_vault = form.cleaned_data["target_vault"]
        try:
            CredentialService.move_to_vault(credential=credential, vault=target_vault)
        except DuplicateCredential as exc:
            form.add_error("target_vault", str(exc))
            return render(request, self.template_name, {
                "form": form,
                "vault": source_vault,
                "credential": credential,
                "detail_url": detail_url,
            })

        return redirect(
            "credential_app:detail",
            username=request.user.username,
            vault_slug=target_vault.slug,
            pk=credential.pk,
        )
