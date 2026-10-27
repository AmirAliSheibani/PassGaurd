from django.db.models import Count
from django.shortcuts import render
from django.urls import reverse

from vault_app.selectors.vault_selector import CategorySelector, VaultSelector


def home_view(request):
    """Render the public landing page or authenticated workspace dashboard."""
    context = {"vault_create_url": reverse("vault_app:create")}

    if request.user.is_authenticated:
        vaults = list(
            VaultSelector.get_user_vaults(user_id=request.user.pk)
            .annotate(credential_count=Count("credentials"))
            .order_by("-is_default", "name")
        )
        context.update(
            {
                "vaults": vaults,
                "vault_count": len(vaults),
                "total_credential_count": sum(vault.credential_count for vault in vaults),
                "category_count": CategorySelector.count(user_id=request.user.pk),
            }
        )

    return render(request, "core/home.html", context)
