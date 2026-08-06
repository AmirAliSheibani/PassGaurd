from django import forms
from django.core.exceptions import ValidationError
from vault_app.models import Vault, Category
from .models import Credential
from common.security.password_generator import PasswordGenerator

default_password_length = PasswordGenerator.DEFAULT_LENGTH


class CredentialBaseForm(forms.Form):
    service_name = forms.CharField(max_length=100, strip=True, widget=forms.TextInput(attrs={
       "class": "form-control", "placeholder": "Service name", "autocomplete": "off"
    }),)
    service_url = forms.URLField(required=False, widget=forms.URLInput(attrs={
        "class": "form-control", "placeholder": "https://example.com", "autocomplete": "off"
    }))
    login_username = forms.CharField(max_length=100, strip=True, widget=forms.TextInput(attrs={
        "class": "form-control", "placeholder": "Username", "autocomplete": "off"
    }))
    login_email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={
        "class": "form-control", "placeholder": "Email", "autocomplete": "off"
    }))
    category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        required=False, empty_label="No category",
        widget=forms.Select(attrs={
            "class": "form-control"
        })
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={
        "rows": "4", "class": "form-control", "placeholder": "Notes", "autocomplete": "off"
    }))
    is_favorite = forms.BooleanField(required=False, initial=False,widget=forms.CheckboxInput(attrs={
        "class": "form-control"
    }))


    def __init__(self, *args, user=None, vault=None, credential=None, **kwargs):
        self.user = user
        self.vault = vault
        self.credential = credential
        super().__init__(*args, **kwargs)

        if self.user is not None:
            self.fields['category'].queryset = (
                Category.objects.filter(user=self.user)
            )
        else:
            self.fields['category'].queryset = Category.objects.none()

    def clean_service_name(self):
        service_name = " ".join(self.cleaned_data["service_name"].split())
        if not service_name:
            raise ValidationError("Service name is required")
        return service_name

    def clean_login_email(self):
        return " ".join(self.cleaned_data["login_email"].split())

    def clean_notes(self):
        notes = self.cleaned_data.get("notes", "")
        return notes.strip()

    def validate_duplicate_in_vault(self, *, service_name: str):
        if self.vault is None:
            return

        qs = Credential.objects.filter(vault=self.vault, service_name=service_name)

        if self.credential is not None:
            qs = qs.exclude(pk=self.credential.id)

        if qs.exists():
            raise ValidationError("Credential with this name already exists")


class CredentialCreateForm(CredentialBaseForm):
    password = forms.CharField(min_length=default_password_length, strip=False, widget=forms.PasswordInput(attrs={
        "class": "form-control", "placeholder": "Password", "autocomplete": "new-password"
    }))
    confirm_password = forms.CharField(min_length=default_password_length, strip=False, widget=forms.PasswordInput(attrs={
        "class": "form-control", "placeholder": "Confirm Password", "autocomplete": "new-password"
    }))

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        service_name = cleaned_data.get("service_name")

        if password and confirm_password and password != confirm_password:
            raise ValidationError({
                "confirm_password": "Passwords do not match."
            })

        if service_name:
            self.validate_duplicate_in_vault(service_name=service_name)

        return cleaned_data


class CredentialUpdateForm(CredentialBaseForm):
    def clean(self):
        cleaned_data = super().clean()
        service_name = cleaned_data.get("service_name")

        if service_name:
            self.validate_duplicate_in_vault(service_name=service_name)

        return cleaned_data


class CredentialRotatePasswordForm(forms.Form):
    new_password = forms.CharField(min_length=default_password_length, strip=False, widget=forms.PasswordInput(attrs={
        "class": "form-control", "placeholder": "New Password", "autocomplete": "new-password"
    }))
    confirm_new_password = forms.CharField(min_length=default_password_length, strip=False, widget=forms.PasswordInput(attrs={
        "class": "form-control", "placeholder": "Confirm New Password", "autocomplete": "new-password"
    }))


    def clean(self):
        cleaned_data = super().clean()

        new_new_password = cleaned_data.get("new_password")
        confirm_new_password = cleaned_data.get("confirm_new_password")

        if new_new_password and confirm_new_password and new_new_password != confirm_new_password:
            raise ValidationError({
                "confirm_new_password": "Passwords do not match."
            })

        return cleaned_data


class CredentialMoveToVaultForm(forms.Form):
    target_vault = forms.ModelChoiceField(
        queryset=Vault.objects.none(),
        empty_label="Select vault",
    )

    def __init__(self, *args, user=None, credential=None, **kwargs):
        self.user = user
        self.credential = credential
        super().__init__(*args, **kwargs)


    def clean_target_vault(self):
        target_vault = self.cleaned_data["target_vault"]

        if self.credential is not None:
            if target_vault == self.credential.vault:
                raise ValidationError("This Credential is already in that Vault")

            duplicate_exsist = Credential.objects.filter(
                vault=self.credential.vault,
                service_name__iexact=self.credential.service_name,
            ).exclude(pk=self.credential.id).exists()

            if duplicate_exsist:
                raise ValidationError(
                    "A Credential with this service name already exists in the target Vault."
                )

        return target_vault


