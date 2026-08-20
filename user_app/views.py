from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.urls import is_valid_path
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from user_app.forms import LoginForm, RegisterForm, BackupCodeConfirmationForm, BackupCodeVerificationForm, \
    ResetPasswordForm, RegenerateBackupCodesForm
from user_app.models import BackupCode
from user_app.selectors.user_selector import UserSelector
from user_app.services.backup_code_service import BackupCodeService
from user_app.services.user_services import UserService


# Create your views here.


class LoginView(View):

    template_name = 'user_app/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("core:home")

        form = LoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        user = authenticate(
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password']
        )

        if user is None:
            form.add_error(None, "Invalid username or password")

            return render(request, self.template_name, {'form': form})

        login(request, user)
        return render(request, self.template_name, {'form': form})


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("core:home")

    def post(self, request):
        logout(request)

        return redirect("core:home")


class RegisterView(View):
    template_name = 'user_app/register.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("core:home")

        form = RegisterForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        user = UserService.register(
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password']
        )
        login(request, user)
        return redirect("core:home")


class BackupCodeSetupView(View):
    """
    Generate the initial recovery codes after registration.
    """
    template_name = 'user_app/backup_code_setup.html'
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("user_app:login")

        if not request.session.get('backup_codes'):
            codes = BackupCodeService.generate(user=request.user)
            request.session['backup_codes'] = codes
        else:
            codes = request.session['backup_codes']

        return render(request, self.template_name, {'codes': codes, 'form': BackupCodeConfirmationForm})

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("user_app:login")

        form = BackupCodeConfirmationForm(request.POST)

        if not form.is_valid():
            codes = request.session.get('backup_codes')

            if not codes:
                return redirect("user_app:backup_code_setup")

            return render(request, self.template_name, {'codes': codes, 'form': form})

        request.session.pop('backup_codes', None)

        return redirect("core:home")


class BackupCodeRecoveryView(View):
    """
    Verifies a backup code and establish a temporary recovery session.
    """
    template_name = 'user_app/backup_code_recovery.html'
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("core:home")

        form = BackupCodeVerificationForm()

        return render(request, self.template_name, {'form': form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect("core:home")

        form = BackupCodeVerificationForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        username = request.POST.get("username", "").strip()

        if not username:
            form.add_error(None, "Username is required.")
            return render(request, self.template_name, {'form': form})

        user = UserSelector.get_by_username(username=username)

        if user is None:
            form.add_error(None, "Invalid recovery credentials.")
            return render(request, self.template_name, {'form': form})

        is_valid = BackupCodeService.verify(user=user, code=form.cleaned_data['code'])

        if not is_valid:
            form.add_error(None, "Invalid recovery credentials.")
            return render(request, self.template_name, {'form': form})

        request.session["recovery_user_id"] = user.pk

        return redirect("user_app:reset-master-password")


class ResetMasterPasswordView(View):
    """
    Allows a user who successfully completed recovery
    to set a new master password.
    """
    template_name = 'user_app/reset_master_password.html'

    def get(self, request):
        user_id = request.session.get("recovery_user_id")

        if not user_id:
            return redirect("user_app:recover")

        form = ResetMasterPasswordView()

        return render(request, self.template_name, {'form': form})

    def post(self, request):
        user_id = request.session.get("recovery_user_id")

        if not user_id:
            return redirect("user_app:recover")

        form = ResetPasswordForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        user = UserSelector.get_by_id(user_id=user_id)

        if user is None:
            request.session.pop("recovery_user_id", None)
            return redirect("user_app:recover")

        UserService.change_password(user=user, password=form.cleaned_data['password'])

        request.session.pop("recovery_user_id", None)

        login(request, user)

        return redirect("user_app:backup_code_setup")


class RegenerateBackupCodesView(View):
    """
    Regenerates the authenticated user's backup codes.

    Rate limiting and authorization belong to the service/security
    layer and must not rely only on UI restrictions.
    """

    template_name = "user_app/regenerate_backup_codes.html"

    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("user_app:login")

        form = RegenerateBackupCodesForm()

        return render(
            request,
            self.template_name,
            {"form": form},
        )

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("user_app:login")

        form = RegenerateBackupCodesForm(
            request.POST
        )

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"form": form},
            )

        codes = BackupCodeService.regenerate(
            user=request.user,
        )

        request.session["backup_codes"] = codes

        return redirect(
            "user_app:backup_code_setup"
        )