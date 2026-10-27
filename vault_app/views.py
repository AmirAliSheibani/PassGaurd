from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count

from .exceptions import DuplicateCategoryExceptions, DuplicateVaultExceptions
from .forms import CategoryForm, VaultForm
from .selectors.vault_selector import VaultSelector, CategorySelector
from .services.vault_service import VaultService, CategoryService
from common.mixins.vaults import VaultObjectMixin, CategoryObjectMixin
from credential_app.selectors.credential_selector import CredentialSelector


class VaultListView(LoginRequiredMixin, TemplateView):
    """Display all vaults belonging to the authenticated user."""
    template_name = "vault_app/vault_list.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["vaults"] = (
            VaultSelector.get_user_vaults(user_id=self.request.user.pk)
            .annotate(credential_count=Count("credentials"))
            .order_by("-is_default", "name")
        )
        context["create_url"] = reverse("vault_app:create")
        return context


class VaultDetailView(LoginRequiredMixin, VaultObjectMixin, TemplateView):
    """Display a vault and a preview of its credentials."""
    template_name = "vault_app/vault_detail.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vault = self.get_vault()
        credentials = CredentialSelector.get_by_vault(vault=vault)
        context.update(
            {
                "vault": vault,
                "credentials": credentials,
                "credential_count": CredentialSelector.count(vault=vault),
                "favorite_count": credentials.filter(is_favorite=True).count(),
                "create_credential_url": reverse(
                    "credential_app:create",
                    kwargs={"username": self.request.user.username, "vault_slug": vault.slug},
                ),
            }
        )
        return context


class VaultCreateView(LoginRequiredMixin, View):
    """Create a new vault for the authenticated user."""
    template_name = "vault_app/vault_form.html"
    login_url = "user_app:login"

    def get(self, request):
        form = VaultForm(user=request.user)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "form_heading": "Create a vault",
                "form_description": "Start a new collection for related credentials.",
                "submit_label": "Create vault",
                "cancel_url": reverse("vault_app:list"),
            },
        )

    def post(self, request):
        form = VaultForm(request.POST, user=request.user)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "form_heading": "Create a vault",
                    "form_description": "Start a new collection for related credentials.",
                    "submit_label": "Create vault",
                    "cancel_url": reverse("vault_app:list"),
                },
            )

        try:
            vault = VaultService.create(
                user=request.user,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                is_default=form.cleaned_data["is_default"],
            )
        except DuplicateVaultExceptions as exc:
            form.add_error("name", str(exc))
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "form_heading": "Create a vault",
                    "form_description": "Start a new collection for related credentials.",
                    "submit_label": "Create vault",
                    "cancel_url": reverse("vault_app:list"),
                },
            )

        return redirect("vault_app:detail", username=vault.user.username, vault_slug=vault.slug)


class VaultUpdateView(LoginRequiredMixin, VaultObjectMixin, View):
    """Update a vault owned by the authenticated user."""
    template_name = "vault_app/vault_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        vault = self.get_vault()
        form = VaultForm(
            user=request.user,
            vault=vault,
            initial={"name": vault.name, "description": vault.description, "is_default": vault.is_default},
        )
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "vault": vault,
                "form_heading": "Edit vault",
                "form_description": "Update the name and settings for this vault.",
                "submit_label": "Save changes",
                "cancel_url": vault.get_absolute_url(),
            },
        )

    def post(self, request, *args, **kwargs):
        vault = self.get_vault()
        form = VaultForm(request.POST, user=request.user, vault=vault)
        page_context = {
            "form_heading": "Edit vault",
            "form_description": "Update the name and settings for this vault.",
            "submit_label": "Save changes",
            "cancel_url": vault.get_absolute_url(),
        }
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "vault": vault, **page_context})

        try:
            VaultService.update(vault=vault, **form.cleaned_data)
        except DuplicateVaultExceptions as exc:
            form.add_error("name", str(exc))
            return render(request, self.template_name, {"form": form, "vault": vault, **page_context})

        return redirect("vault_app:detail", username=vault.user.username, vault_slug=vault.slug)


class VaultDeleteView(LoginRequiredMixin, VaultObjectMixin, View):
    """Delete a vault owned by the authenticated user. Deletion is POST-only."""
    template_name = "vault_app/vault_confirm_delete.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {"vault": self.get_vault()})

    def post(self, request, *args, **kwargs):
        VaultService.delete(vault=self.get_vault())
        return redirect("vault_app:list")


class CategoryCreateView(LoginRequiredMixin, View):
    """Create a category for the authenticated user."""
    template_name = "vault_app/category_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        form = CategoryForm(user=request.user)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "form_heading": "Create a category",
                "form_description": "Add a label to organize credential entries.",
                "submit_label": "Create category",
                "cancel_url": reverse("vault_app:categories"),
            },
        )

    def post(self, request):
        form = CategoryForm(request.POST, user=request.user)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "form_heading": "Create a category",
                    "form_description": "Add a label to organize credential entries.",
                    "submit_label": "Create category",
                    "cancel_url": reverse("vault_app:categories"),
                },
            )

        try:
            CategoryService.create(user=request.user, **form.cleaned_data)
        except DuplicateCategoryExceptions as exc:
            form.add_error("name", str(exc))
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "form_heading": "Create a category",
                    "form_description": "Add a label to organize credential entries.",
                    "submit_label": "Create category",
                    "cancel_url": reverse("vault_app:categories"),
                },
            )
        return redirect("vault_app:categories")


class CategoryUpdateView(LoginRequiredMixin, CategoryObjectMixin, View):
    """Update a category owned by the authenticated user."""
    template_name = "vault_app/category_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        category = self.get_category()
        form = CategoryForm(user=request.user, category=category, initial={"name": category.name, "color": category.color})
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "category": category,
                "form_heading": "Edit category",
                "form_description": "Update this category's name or color.",
                "submit_label": "Save changes",
                "cancel_url": reverse("vault_app:categories"),
            },
        )

    def post(self, request, *args, **kwargs):
        category = self.get_category()
        form = CategoryForm(request.POST, user=request.user, category=category)
        page_context = {
            "category": category,
            "form_heading": "Edit category",
            "form_description": "Update this category's name or color.",
            "submit_label": "Save changes",
            "cancel_url": reverse("vault_app:categories"),
        }
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, **page_context})

        try:
            CategoryService.update(category=category, **form.cleaned_data)
        except DuplicateCategoryExceptions as exc:
            form.add_error("name", str(exc))
            return render(request, self.template_name, {"form": form, **page_context})
        return redirect("vault_app:categories")


class CategoryListView(LoginRequiredMixin, TemplateView):
    """Display the authenticated user's categories."""
    template_name = "vault_app/category_list.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = CategorySelector.get_user_categories(user_id=self.request.user.pk)
        context["create_url"] = reverse("vault_app:category_create")
        return context


class CategoryDeleteView(LoginRequiredMixin, CategoryObjectMixin, View):
    """Delete a category belonging to the authenticated user."""
    template_name = "vault_app/category_confirm_delete.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {"category": self.get_category()})

    def post(self, request, *args, **kwargs):
        CategoryService.delete(category=self.get_category())
        return redirect("vault_app:categories")
