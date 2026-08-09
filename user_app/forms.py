from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150, strip=True, widget=forms.TextInput(attrs={
        'class': 'form-control', "placeholder": "Username", "autofocus": True, "autocomplete": "username"
    }))
    password = forms.CharField(strip=False ,widget=forms.PasswordInput(attrs={
        'class': 'form-control', "placeholder": "Master password", "autocomplete": "current-password"
    }))

    def clean_username(self):
        return self.cleaned_data["username"].strip()


class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150, min_length=3, strip=True, widget=forms.TextInput(attrs={
        'class': 'form-control', "placeholder": "Username", "autofocus": True, "autocomplete": "username"
    }))
    password = forms.CharField(min_length=12, strip=False ,widget=forms.PasswordInput(attrs={
        'class': 'form-control', "placeholder": "Master password", "autocomplete": "new-password"
    }))
    confirm_password = forms.CharField(min_length=12, strip=False, widget=forms.PasswordInput(attrs={
        'class': 'form-control', "placeholder": "Confirm master password", "autocomplete": "new-password"
    }))

    def clean_username(self):
        username = " ".join(self.cleaned_data["username"].split())

        if not username:
            raise ValidationError("Username is required")

        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")

        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error(confirm_password, "Passwords don't match")

        return cleaned_data



