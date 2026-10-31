from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from common.mixins.vaults import CategoryObjectMixin, VaultObjectMixin
from credential_app.selectors.credential_selector import CredentialSelector
from .exceptions import DuplicateCategoryExceptions, DuplicateVaultExceptions
from .forms import CategoryForm, VaultForm
from .selectors.vault_selector import CategorySelector, VaultSelector
from .services.vault_service import CategoryService, VaultService


def _vault_form_context(*, form, vault=None):
    is_update = vault is not None
    return {
        "form": form,
        "vault": vault,
        "form_heading": "Edit vault" if is_update else "Create vault",
        "form_description": (
            "Update the name and organization details for this vault."
            if is_update
            else "Create a space for a related group of credentials."
        ),
        "cancel_url": vault.get_absolute_url() if is_update else reverse("vault_app:list"),
        "submit_label": "Save changes" if is_update else "Create vault",
    }


def _category_form_context(*, form, category=None):
    is_update = category is not None
    return {
        "form": form,
        "category": category,
        "form_heading": "Edit category" if is_update else "Create category",
        "form_description": (
            "Update this category's name and visual color."
            if is_update
            else "Create a reusable label for organizing credentials."
        ),
        "cancel_url": reverse("vault_app:categories"),
        "submit_label": "Save changes" if is_update else "Create category",
    }


class VaultListView(LoginRequiredMixin, TemplateView):
    """Display all vaults belonging to the authenticated user."""

    template_name = "vault_app/vault_list.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vaults = (
            VaultSelector.get_user_vaults(user_id=self.request.user.pk)
            .annotate(credential_count=Count("credentials", distinct=True))
            .order_by("-is_default", "name")
        )
        context.update({
            "vaults": vaults,
            "create_url": reverse("vault_app:create"),
        })
        return context


class VaultDetailView(LoginRequiredMixin, VaultObjectMixin, TemplateView):
    """Display a vault and a small preview of its most recently updated credentials."""

    template_name = "vault_app/vault_detail.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vault = self.get_vault()
        credentials = CredentialSelector.get_by_vault(vault=vault)
        context.update({
            "vault": vault,
            "credentials": credentials[:5],
            "credential_count": CredentialSelector.count(vault=vault),
            "favorite_count": CredentialSelector.get_favorites(vault=vault).count(),
            "create_credential_url": reverse(
                "credential_app:create",
                kwargs={"username": self.request.user.username, "vault_slug": vault.slug},
            ),
        })
        return context


class VaultCreateView(LoginRequiredMixin, View):
    """Create a new vault for the authenticated user."""

    template_name = "vault_app/vault_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        form = VaultForm(user=request.user)
        return render(request, self.template_name, _vault_form_context(form=form))

    def post(self, request, *args, **kwargs):
        form = VaultForm(request.POST, user=request.user)
        if not form.is_valid():
            return render(request, self.template_name, _vault_form_context(form=form))

        try:
            vault = VaultService.create(
                user=request.user,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                is_default=form.cleaned_data["is_default"],
            )
        except DuplicateVaultExceptions as exc:
            form.add_error("name", str(exc))
            return render(request, self.template_name, _vault_form_context(form=form))

        return redirect(
            "vault_app:detail",
            username=request.user.username,
            vault_slug=vault.slug,
        )


class VaultUpdateView(LoginRequiredMixin, VaultObjectMixin, View):
    """Update a vault owned by the authenticated user."""

    template_name = "vault_app/vault_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        vault = self.get_vault()
        form = VaultForm(
            user=request.user,
            vault=vault,
            initial={
                "name": vault.name,
                "description": vault.description,
                "is_default": vault.is_default,
            },
        )
        return render(
            request,
            self.template_name,
            _vault_form_context(form=form, vault=vault),
        )

    def post(self, request, *args, **kwargs):
        vault = self.get_vault()
        form = VaultForm(request.POST, user=request.user, vault=vault)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                _vault_form_context(form=form, vault=vault),
            )

        try:
            VaultService.update(vault=vault, **form.cleaned_data)
        except DuplicateVaultExceptions as exc:
            form.add_error("name", str(exc))
            return render(
                request,
                self.template_name,
                _vault_form_context(form=form, vault=vault),
            )

        return redirect(
            "vault_app:detail",
            username=request.user.username,
            vault_slug=vault.slug,
        )


class VaultDeleteView(LoginRequiredMixin, VaultObjectMixin, View):
    """Delete a vault only after a confirmation page and a POST request."""

    template_name = "vault_app/vault_confirm_delete.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {"vault": self.get_vault()})

    def post(self, request, *args, **kwargs):
        vault = self.get_vault()
        VaultService.delete(vault=vault)
        return redirect("vault_app:list")


class CategoryCreateView(LoginRequiredMixin, View):
    """Create a category for the authenticated user."""

    template_name = "vault_app/category_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        form = CategoryForm(user=request.user)
        return render(request, self.template_name, _category_form_context(form=form))

    def post(self, request, *args, **kwargs):
        form = CategoryForm(request.POST, user=request.user)
        if not form.is_valid():
            return render(request, self.template_name, _category_form_context(form=form))

        try:
            CategoryService.create(user=request.user, **form.cleaned_data)
        except DuplicateCategoryExceptions as exc:
            form.add_error("name", str(exc))
            return render(request, self.template_name, _category_form_context(form=form))

        return redirect("vault_app:categories")


class CategoryUpdateView(LoginRequiredMixin, CategoryObjectMixin, View):
    """Update a category belonging to the authenticated user."""

    template_name = "vault_app/category_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        category = self.get_category()
        form = CategoryForm(
            user=request.user,
            category=category,
            initial={"name": category.name, "color": category.color},
        )
        return render(
            request,
            self.template_name,
            _category_form_context(form=form, category=category),
        )

    def post(self, request, *args, **kwargs):
        category = self.get_category()
        form = CategoryForm(request.POST, user=request.user, category=category)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                _category_form_context(form=form, category=category),
            )

        try:
            CategoryService.update(category=category, **form.cleaned_data)
        except DuplicateCategoryExceptions as exc:
            form.add_error("name", str(exc))
            return render(
                request,
                self.template_name,
                _category_form_context(form=form, category=category),
            )

        return redirect("vault_app:categories")


class CategoryListView(LoginRequiredMixin, TemplateView):
    """Display all categories belonging to the authenticated user."""

    template_name = "vault_app/category_list.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "categories": CategorySelector.get_user_categories(
                user_id=self.request.user.pk,
            ),
            "create_url": reverse("vault_app:category_create"),
        })
        return context


class CategoryDeleteView(LoginRequiredMixin, CategoryObjectMixin, View):
    """Delete a category while preserving credentials through SET_NULL."""

    template_name = "vault_app/category_confirm_delete.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {"category": self.get_category()})

    def post(self, request, *args, **kwargs):
        category = self.get_category()
        CategoryService.delete(category=category)
        return redirect("vault_app:categories")
