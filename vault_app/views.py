from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView, CreateView
from django.http import Http404
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Category
from .exceptions import DuplicateCategoryExceptions, DuplicateVaultExceptions
from .forms import CategoryForm, VaultForm
from .selectors.vault_selector import VaultSelector, CategorySelector
from .services.vault_service import VaultService, CategoryService
from common.mixins.vaults import VaultObjectMixin


class VaultListView(LoginRequiredMixin, TemplateView):
    """
    Display all vaults belonging to the authenticated user.
    """
    template_name = "vault_app/vault_list.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["vaults"] = VaultSelector.get_user_vaults(user_id=self.request.user.id)
        return context


class VaultDetailView(LoginRequiredMixin, VaultObjectMixin, TemplateView):
    """
    Display a single vault owned by the authenticated user.
    """
    template_name = "vault_app/vault_detail.html"
    login_url = "user_app:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["vault"] = self.get_vault()
        return context


class VaultCreateView(LoginRequiredMixin, View):
    """
    Create a new vault for the authenticated user.
    """
    template_name = "vault_app/vault_form.html"
    login_url = "user_app:login"

    def get(self, request):
        form = VaultForm(user=self.request.user)

        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = VaultForm(request.POST, user=self.request.user)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            vault = VaultService.create(
                user=request.user,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                is_default=form.cleaned_data["is_default"]
            )
        except DuplicateVaultExceptions as exc:
            form.add_error("name", str(exc))
            return render(request, self.template_name, {"form": form})

        return redirect(
            "vault_app:detail",
            username=vault.user.username,
            vault_slug=vault.slug
        )


class VaultUpdateView(LoginRequiredMixin, VaultObjectMixin, View):
    """
    Update a vault owned by the authenticated user.
    """
    template_name = "vault_app/vault_form.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        vault = self.get_vault()
        form = VaultForm(user=self.request.user, vault=vault, initial={
            "name": vault.name,
            "description": vault.description,
            "is_default": vault.is_default,
        })
        return render(request, self.template_name, {"form": form})

    def post(self, request, *args, **kwargs):
        vault = self.get_vault()
        form = VaultForm(request.POST, user=request.user, vault=vault)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "vault": vault})

        try:
            updated_vault = VaultService.update(
                user_id=request.user,
                data={
                    "pk": vault.pk,
                    **form.cleaned_data,
                }
            )
        except DuplicateVaultExceptions as exc:
            form.add_error("name", str(exc))

            return render(request, self.template_name, {"form": form, "vault": vault})

        return redirect(
            "vault_app:detail",
            username=vault.user.username,
            vault_slug=vault.slug
        )

class VaultDeleteView(LoginRequiredMixin, VaultObjectMixin, View):
    """
    Delete a vault owned by the authenticated user.

    Deletion is performed only through POST.
    """
    template_name = "vault_app/vault_confirm_delete.html"
    login_url = "user_app:login"

    def get(self, request, *args, **kwargs):
        vault = self.get_vault()
        return render(request, self.template_name, {"vault": vault})

    def post(self, request, *args, **kwargs):
        vault = self.get_vault()

        VaultService.delete(user_id=request.user, data={"pk": vault.pk})
        return redirect("vault_app:list")


class CategoryCreateView(LoginRequiredMixin, View):
     """
    Create a category for the authenticated user.
    """
     template_name = "vault_app/category_form.html"
     login_url = "user_app:login"

     def get(self, request, *args, **kwargs):
         form = CategoryForm(user=self.request.user)
         return render(request, self.template_name, {"form": form})

     def post(self, request):
         form = CategoryForm(request.POST, user=self.request.user)

         if not form.is_valid():
             return render(request, self.template_name, {"form": form})

         try:
             category = CategoryService.create(
                 user_id=request.user.id,
                 data=form.cleaned_data,
             )
         except DuplicateCategoryExceptions as exc:
             form.add_error("name", str(exc))
             return render(request, self.template_name, {"form": form})

         return redirect(
             "vault_app:categories"
         )


class CategoryUpdateView(LoginRequiredMixin, View):
    """
    Create a category for the authenticated user.
    """
    template_name = "vault_app/category_form.html"
    login_url = "user_app:login"

    def _get_category(self, request, category_id):
        try:
            return CategorySelector.get_by_id_for_user(
                category_id=category_id,
                user_id=request.user.id
            )
        except Category.DoesNotExist:
            raise Http404

    def get(self, request, category_id):
        category = self._get_category(request, category_id)

        form = CategoryForm(user=request.user, category=category, initial={
            "name": category.name,
            "color": category.color,
        })
        return render(request, self.template_name, {"form": form})


    def post(self, request, category_id):
        category = self._get_category(request, category_id)
        form = CategoryForm(request.POST, user=request.user, category=category)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "category": category})

        try:
            CategoryService.update(
                user_id=request.user.id,
                data={
                    "pk": category.pk,
                    **form.cleaned_data,
                }
            )
        except DuplicateCategoryExceptions as exc:
            form.add_error("name", str(exc))
            return render(request, self.template_name, {"form": form, "category": category})

        return redirect(
            "vault_app:categories",
        )


