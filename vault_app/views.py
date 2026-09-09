from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView
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



