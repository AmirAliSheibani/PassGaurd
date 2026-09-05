from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.views import View

from user_app.forms import LoginForm, RegisterForm, BackupCodeConfirmationForm, BackupCodeVerificationForm, \
    ResetPasswordForm, RegenerateBackupCodesForm

from user_app.selectors.user_selector import UserSelector
from user_app.services.backup_code_service import BackupCodeService
from user_app.services.user_services import UserService

from common.security.rate_limit.exceptions import RateLimitExceeded, CooldownActive
from common.security.rate_limit.limiter import RateLimiter
from common.security.rate_limit.policies import LoginRateLimitPolicy, RecoveryRateLimitPolicy


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

        username = form.cleaned_data['username']
        password = form.cleaned_data['password']

        try:
            # Limit all login requests from the same IP.
            RateLimiter.consume(
                action="login:ip",
                identifier=request.META.get("REMOTE_ADDR", "unknown"),
                limit=LoginRateLimitPolicy.IP_LIMIT,
                window=LoginRateLimitPolicy.IP_WINDOW,
            )
            # Only failed authentication attempts are counted for the username.
            RateLimiter.check(
                action="login:username",
                identifier=username.lower(),
                limit=LoginRateLimitPolicy.USERNAME_FAILURE_LIMIT,
            )
        except RateLimitExceeded:
            form.add_error(None, "Too many attempts. Please try again later.")
            return render(request, self.template_name, {'form': form})

        user = authenticate(
            request=request,
            username=username,
            password=password
        )

        if user is None:
            RateLimiter.record_failure(
                action="login:username",
                identifier=username.lower(),
                window=LoginRateLimitPolicy.USERNAME_FAILURE_WINDOW,
            )

            form.add_error(None, "Invalid username or password")
            return render(request, self.template_name, {'form': form})

        # When Everything is OK.
        RateLimiter.reset(action="login:username", identifier=username.lower())
        login(request, user)
        if not user.recovery_setup_completed:
            request.session["backup_code_setup_pending"] = True
            return redirect("user_app:backup_code_setup")

        return redirect("core:home")


class LogoutView(View):

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
        return redirect("user_app:backup_code_setup")


class BackupCodeSetupView(View):
    """
    Generate the initial recovery codes after registration.
    """
    template_name = 'user_app/backup_code_setup.html'
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("user_app:login")


        if not request.session.get('backup_codes'):
            pending = request.session.get("backup_code_setup_pending", False)
            if request.user.recovery_setup_completed and not pending:
                return redirect("core:home")

            codes = BackupCodeService.generate(user=request.user)
            request.session['backup_codes'] = codes
        else:
            codes = request.session['backup_codes']

        request.session["backup_code_setup_pending"] = True

        # Recovery codes are sensitive and should not remain available indefinitely in the server-side session.
        request.session.set_expiry(600)

        return render(request, self.template_name, {'codes': codes, 'form': BackupCodeConfirmationForm()})

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("user_app:login")

        form = BackupCodeConfirmationForm(request.POST)

        if not form.is_valid():
            codes = request.session.get('backup_codes')

            if not codes:
                return redirect("user_app:backup_code_setup")

            request.session.set_expiry(600)
            return render(request, self.template_name, {'codes': codes, 'form': form})

        # Finish setup
        UserService.mark_recovery_setup_completed(
            user=request.user,
        )
        request.session.pop("backup_codes", None)
        request.session.pop(
            "backup_code_setup_pending",
            None,
        )

        request.session.set_expiry(None)
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

        username = form.cleaned_data["username"]
        code = form.cleaned_data["code"]

        try:
            RateLimiter.consume(
                action="recovery:ip",
                identifier=request.META.get(
                    "REMOTE_ADDR",
                    "unknown",
                ),
                limit=RecoveryRateLimitPolicy.IP_LIMIT,
                window=RecoveryRateLimitPolicy.IP_WINDOW,
            )

            RateLimiter.check(
                action="recovery:username",
                identifier=username.lower(),
                limit=RecoveryRateLimitPolicy.USERNAME_FAILURE_LIMIT
            )

        except RateLimitExceeded:
            form.add_error(
                None,
                "Too many recovery attempts. Please try again later.",
            )

            return render(
                request,
                self.template_name,
                {"form": form},
            )

        user = UserSelector.get_by_username(username=username)

        # Deliberately do not reveal whether the username exists.
        if user is None:
            RateLimiter.record_failure(
                action="recovery:username",
                identifier=username.lower(),
                window=RecoveryRateLimitPolicy.USERNAME_FAILURE_WINDOW,
            )
            form.add_error(None, "Invalid recovery credentials.")
            return render(request, self.template_name, {'form': form})


        is_valid = BackupCodeService.verify(user=user, code=code)

        if not is_valid:
            RateLimiter.record_failure(
                action="recovery:username",
                identifier=username.lower(),
                window=RecoveryRateLimitPolicy.USERNAME_FAILURE_WINDOW,
            )

            form.add_error(None, "Invalid recovery credentials.")
            return render(request, self.template_name, {'form': form})

        RateLimiter.reset(
            action="recovery:username",
            identifier=username.lower(),
        )

        # Prevent reuse of the previous anonymous session.
        request.session.cycle_key()
        request.session["recovery_user_id"] = user.pk
        # Recovery authorization should be short-lived.
        request.session.set_expiry(600)     

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

        form = ResetPasswordForm()

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
            request.session.flush()
            return redirect("user_app:recover")

        UserService.change_password(user=user, new_password=form.cleaned_data['password'])

        request.session.flush()

        login(request, user)

        request.session["backup_code_setup_pending"] = True
        request.session.set_expiry(600)

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

        try:
            codes = BackupCodeService.regenerate(
                user=request.user,
            )
        except CooldownActive:
            form.add_error(
                None,
                "Backup codes were recently regenerated, Please try again later."
            )
            return render(request, self.template_name, {'form': form})

        request.session["backup_codes"] = codes

        return redirect(
            "user_app:backup_code_setup"
        )
