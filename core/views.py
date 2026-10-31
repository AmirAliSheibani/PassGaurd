from django.db.models import Count
from django.shortcuts import render
from django.urls import reverse

from credential_app.selectors.credential_selector import CredentialSelector
from vault_app.selectors.vault_selector import CategorySelector, VaultSelector


def home_view(request):
    """Render the public landing page or the authenticated workspace dashboard."""
    context = {}

    if request.user.is_authenticated:
        user_id = request.user.pk
        vaults = (
            VaultSelector.get_user_vaults(user_id=user_id)
            .annotate(credential_count=Count("credentials", distinct=True))
            .order_by("-is_default", "name")
        )

        context = {
            "vaults": vaults,
            "vault_count": vaults.count(),
            "total_credential_count": CredentialSelector.count_for_user(
                user_id=user_id,
            ),
            "category_count": CategorySelector.count(user_id=user_id),
            "vault_create_url": reverse("vault_app:create"),
        }

    return render(request, "core/home.html", context)
