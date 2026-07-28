from django.contrib import admin
from .models import  Vault,Category
# Register your models here.

@admin.register(Vault)
class VaultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "user",
        "is_default",
        "created_at",
    )
    list_filter = (
        "is_default",
        "created_at",
    )
    search_fields = (
        "name",
        "user__username",
        "user__email",
    )
    ordering = ("user", "-created_at",)
    readonly_fields = ("created_at",)
    list_select_related = ("user",)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
    )
    list_filter = (
        "created_at",
    )
    search_fields = (
        "name",
        "user__username",
        "user__email",
    )
    ordering = ("user", "-created_at",)
    readonly_fields = ("created_at",)
    list_select_related = ("user",)

