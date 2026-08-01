from django import forms
from .models import Vault, Category
from django.core.exceptions import ValidationError


class VaultForm(forms.Form):

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    name = forms.CharField(max_length=100, strip=True, widget=forms.TextInput(
        attrs={"class": "form-control", "autofocus": True, "autocomplete": "off",
               "placeholder": "Vault name"}
    ),)

    description = forms.CharField(required=False, widget=forms.Textarea(
        attrs={"class": "form-control", "autofocus": True, "autocomplete": "off", "rows": 4}
    ),)
    is_default = forms.BooleanField(required=False, initial=False)


    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if not name:
            raise ValueError("Vault name is required")

        if self.user and Vault.objects.filter(user=self.user, name__iexact=name).exists():
            raise ValidationError("You already have a vault with this name.")

        return name


    def clean_description(self):
        description = self.cleaned_data.get("description", "")
        return description.strip()


class CategoryForm(forms.Form):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    name = forms.CharField(max_length=100, strip=True, widget=forms.TextInput(
        attrs={"class": "form-control", "autofocus": True, "autocomplete": "off", "placeholder": "Category name"}
    ))

    color = forms.RegexField(
        regex=r"^#[0-9A-Fa-f]{6}$",
        initial="#6B7280",
        widget=forms.TextInput(attrs={
            "placeholder": "#6B7280",
            "autocomplete": "off",
        }),
        error_messages={
            "invalid": "Color must be a valid HEX code like #6B7280.",
        },
    )


    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if not name:
            raise ValueError("Category name is required")

        if self.user and Category.objects.filter(user=self.user, name__iexact=name).exists():
            raise ValidationError("You already have a category with this name.")

        return name


    def clean_color(self):
        return self.cleaned_data["color"].upper()
    