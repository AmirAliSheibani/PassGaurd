from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model, password_validation

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

        try:
            username = User._meta.get_field("username").clean(username, None)
        except ValidationError as exc:
            raise ValidationError(exc.messages)

        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")

        return username

    def clean_password(self):
        password = self.cleaned_data["password"]
        username = self.cleaned_data.get("username", "")
        try:
            password_validation.validate_password(
                password,
                user=User(username=username),
            )
        except ValidationError as exc:
            raise ValidationError(exc.messages)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords don't match")

        return cleaned_data


class ResetPasswordForm(forms.Form):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    password = forms.CharField(min_length=12, strip=False, widget=forms.PasswordInput(attrs={
        'class': 'form-control', "placeholder": "Master password", "autocomplete": "new-password"
    }))
    confirm_password = forms.CharField(min_length=12, strip=False, widget=forms.PasswordInput(attrs={
        'class': 'form-control', "placeholder": "Confirm master password", "autocomplete": "new-password"
    }))

    def clean_password(self):
        password = self.cleaned_data["password"]
        try:
            password_validation.validate_password(password, user=self.user)
        except ValidationError as exc:
            raise ValidationError(exc.messages)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords don't match")

        return cleaned_data


class BackupCodeVerificationForm(forms.Form):
    """
    validates a single backup code during account recovery.
    """
    code = forms.CharField(min_length=12, max_length=12, strip=True, widget=forms.TextInput(attrs={
        'class': 'form-control', "inputmode": "numeric", "placeholder": "12-digit backup code", "autocomplete": "one-time-code"
    }))

    username = forms.CharField(max_length=150, min_length=3, strip=True, widget=forms.TextInput(attrs={
        'class': 'form-control', "placeholder": "Username", "autofocus": True, "autocomplete": "username"
    }))

    def clean_username(self):
        username = self.cleaned_data['username'].strip()

        if not username:
            self.add_error(None, "Username is required.")

        return username

    def clean_code(self):
        code = self.cleaned_data["code"].strip()

        if not code.isascii() or not code.isdigit():
            raise ValidationError("Backup code must contain ASCII digits only.")

        if len(code) != 12:
            raise ValidationError("backup code must contain 12 digits")

        return code


class BackupCodeConfirmationForm(forms.Form):
    """
    Confirm that the user has successfully stored the backup code.
    """
    confirmed = forms.BooleanField(
        required=True,
        label="I have securely saved my backup codes.",
        widget=forms.CheckboxInput(attrs={
           'class': 'form-control', "autocomplete": "off"
        }),
        error_messages={
            'required': "You must confirm that you have saved your backup codes."
        },
    )


class RegenerateBackupCodesForm(forms.Form):
    """
    confirms the user's backup codes intentions before generating new backup codes.
    """

    confirmation = forms.BooleanField(
        required=True,
        label="I understand that my existing backup codes will become invalid.",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-control', "autocomplete": "off"
        }),
        error_messages={
            "required": "You must confirm that you want to regenerate your backup codes."
        },
    )

