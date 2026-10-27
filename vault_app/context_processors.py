"""Small, reusable navigation context for the authenticated PassGuard shell."""

def navigation_context(request):
    """Expose a short, owner-scoped vault list for the persistent sidebar.

    Only the fields used by navigation are loaded. The list is capped to keep
    every page render predictable; the Vaults page remains the place to browse
    the complete collection.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "sidebar_vaults": (),
            "sidebar_vault_count": 0,
        }

    vaults = user.vaults.only(
        "id",
        "name",
        "slug",
        "is_default",
    ).order_by("-is_default", "name")

    return {
        "sidebar_vaults": vaults[:5],
        "sidebar_vault_count": vaults.count(),
    }
