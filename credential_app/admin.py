from django.contrib import admin

from .models import Credential, CredentialHistory


@admin.register(Credential)
class CredentialAdmin(admin.ModelAdmin):
    list_display = (
        "service_name",
        "vault",
        "category",
        "login_username",
        "login_email",
        "is_favorite",
        "updated_at",
    )

    search_fields = (
        "service_name",
        "login_username",
        "login_email",
        "vault__name",
        "vault__user__username",
        "category__name",
    )

    list_filter = (
        "is_favorite",
        "category",
        "vault",
    )

    ordering = (
        "-updated_at",
    )

    list_select_related = (
        "vault",
        "vault__user",
        "category",
    )

    autocomplete_fields = (
        "vault",
        "category",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    list_per_page = 50

    save_on_top = True

    fieldsets = (
        (
            "Credential Information",
            {
                "fields": (
                    "vault",
                    "category",
                    "service_name",
                    "service_url",
                )
            },
        ),
        (
            "Login Information",
            {
                "fields": (
                    "login_username",
                    "login_email",
                    "password_ciphertext",
                )
            },
        ),
        (
            "Options",
            {
                "fields": (
                    "is_favorite",
                    "notes",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(CredentialHistory)
class CredentialHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "credential",
        "created_at",
    )

    search_fields = (
        "credential__service_name",
        "credential__vault__user__username",
    )

    ordering = (
        "-created_at",
    )

    list_select_related = (
        "credential",
        "credential__vault",
        "credential__vault__user",
    )

    readonly_fields = (
        "credential",
        "old_password_ciphertext",
        "new_password_ciphertext",
        "created_at",
    )

    list_per_page = 50

    fieldsets = (
        (
            "Credential",
            {
                "fields": (
                    "credential",
                )
            },
        ),
        (
            "Password History",
            {
                "fields": (
                    "old_password_ciphertext",
                    "new_password_ciphertext",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

