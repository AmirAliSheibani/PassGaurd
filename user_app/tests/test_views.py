from django.conf import settings
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase

from common.security.rate_limit.exceptions import RateLimitExceeded, CooldownActive
from user_app.views import (
    BackupCodeRecoveryView,
    BackupCodeSetupView,
    LoginView,
    LogoutView,
    RegenerateBackupCodesView,
    RegisterView,
    ResetMasterPasswordView,
)


User = get_user_model()


class FakeResponse:
    """Small response object for isolated view unit tests."""

    def __init__(self, *, url=None, status_code=200, context=None):
        self.url = url
        self.status_code = status_code
        self.context_data = context or {}


def fake_redirect(to, *args, **kwargs):
    """Do not let Django resolve names such as `core:home` in unit tests."""
    return FakeResponse(url=to, status_code=302)


def fake_render(request, template_name, context=None, *args, **kwargs):
    """Return a lightweight render response without requiring real templates."""
    return FakeResponse(
        status_code=200,
        context=context or {},
    )


class UserViewTests(TestCase):
    """Unit-level tests for user_app views."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="amir",
            password="StrongPassword123!",
        )
        cls.user.recovery_setup_completed = False
        cls.user.save(update_fields=["recovery_setup_completed"])

    def setUp(self):
        self.factory = RequestFactory()

    # ------------------------------------------------------------------
    # Request/session helpers
    # ------------------------------------------------------------------

    def _request(self, method, path, *, data=None, user=None, ip="127.0.0.1"):
        if method == "GET":
            request = self.factory.get(path, data=data or {})
        else:
            request = self.factory.post(path, data=data or {})

        request.user = user if user is not None else AnonymousUser()
        request.META["REMOTE_ADDR"] = ip
        request.session = SessionStore()
        request.session.create()
        return request

    def _authenticated_request(self, method="GET", path="/", data=None):
        return self._request(
            method,
            path,
            data=data,
            user=self.user,
        )

    # ------------------------------------------------------------------
    # LoginView GET
    # ------------------------------------------------------------------

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    def test_authenticated_user_is_redirected_from_login(self, mock_redirect):
        request = self._authenticated_request("GET", "/login/")

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "core:home")
        mock_redirect.assert_called_once_with("core:home")

    @patch("user_app.views.render", side_effect=fake_render)
    def test_anonymous_user_can_open_login_page(self, mock_render):
        request = self._request("GET", "/login/")

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context_data["form"].__class__.__name__,
            "LoginForm",
        )
        mock_render.assert_called_once()

    # ------------------------------------------------------------------
    # LoginView POST
    # ------------------------------------------------------------------

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.LoginForm")
    def test_login_invalid_form_is_rendered(self, mock_form_cls, mock_render):
        form = MagicMock()
        form.is_valid.return_value = False
        mock_form_cls.return_value = form

        request = self._request(
            "POST",
            "/login/",
            data={"username": "amir", "password": "bad"},
        )

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_form_cls.assert_called_once_with(request.POST)
        mock_render.assert_called_once()

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.LoginForm")
    @patch("user_app.views.RateLimiter.check")
    @patch("user_app.views.RateLimiter.consume")
    def test_login_rate_limit_exceeded_renders_form_error(
        self,
        mock_consume,
        mock_check,
        mock_form_cls,
        mock_render,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "username": "amir",
            "password": "StrongPassword123!",
        }
        mock_form_cls.return_value = form
        mock_consume.side_effect = RateLimitExceeded

        request = self._request(
            "POST",
            "/login/",
            data={
                "username": "amir",
                "password": "StrongPassword123!",
            },
        )

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        form.add_error.assert_called_once_with(
            None,
            "Too many attempts. Please try again later.",
        )
        mock_check.assert_not_called()
        mock_render.assert_called_once()

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.LoginForm")
    @patch("user_app.views.authenticate", return_value=None)
    @patch("user_app.views.RateLimiter.record_failure")
    @patch("user_app.views.RateLimiter.check")
    @patch("user_app.views.RateLimiter.consume")
    def test_login_invalid_credentials_record_failure(
        self,
        mock_consume,
        mock_check,
        mock_record_failure,
        mock_authenticate,
        mock_form_cls,
        mock_render,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "username": "AmIr",
            "password": "wrong-password",
        }
        mock_form_cls.return_value = form

        request = self._request(
            "POST",
            "/login/",
            data={
                "username": "AmIr",
                "password": "wrong-password",
            },
        )

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 200)

        mock_authenticate.assert_called_once_with(
            request=request,
            username="AmIr",
            password="wrong-password",
        )

        mock_record_failure.assert_called_once()

        self.assertEqual(
            mock_record_failure.call_args.kwargs["action"],
            "login:username",
        )
        self.assertEqual(
            mock_record_failure.call_args.kwargs["identifier"],
            "amir",
        )

        form.add_error.assert_called_once_with(
            None,
            "Invalid username or password",
        )

        mock_render.assert_called_once()

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    @patch("user_app.views.login")
    @patch("user_app.views.authenticate")
    @patch("user_app.views.RateLimiter.reset")
    @patch("user_app.views.RateLimiter.check")
    @patch("user_app.views.RateLimiter.consume")
    @patch("user_app.views.LoginForm")
    def test_login_successfully_redirects_to_backup_setup_when_recovery_is_pending(
        self,
        mock_form_cls,
        mock_consume,
        mock_check,
        mock_reset,
        mock_authenticate,
        mock_login,
        mock_redirect,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "username": "amir",
            "password": "StrongPassword123!",
        }
        mock_form_cls.return_value = form
        mock_authenticate.return_value = self.user

        request = self._request(
            "POST",
            "/login/",
            data={
                "username": "amir",
                "password": "StrongPassword123!",
            },
        )

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "user_app:backup_code_setup")

        self.assertTrue(
            request.session["backup_code_setup_pending"]
        )

        mock_login.assert_called_once_with(
            request,
            self.user,
        )

        mock_reset.assert_called_once_with(
            action="login:username",
            identifier="amir",
        )

        mock_redirect.assert_called_once_with(
            "user_app:backup_code_setup"
        )

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    @patch("user_app.views.login")
    @patch("user_app.views.authenticate")
    @patch("user_app.views.RateLimiter.reset")
    @patch("user_app.views.RateLimiter.check")
    @patch("user_app.views.RateLimiter.consume")
    @patch("user_app.views.LoginForm")
    def test_login_successfully_redirects_home_when_recovery_is_complete(
        self,
        mock_form_cls,
        mock_consume,
        mock_check,
        mock_reset,
        mock_authenticate,
        mock_login,
        mock_redirect,
    ):
        user = User.objects.create_user(
            username="ready-user",
            password="StrongPassword123!",
        )

        user.recovery_setup_completed = True
        user.save(update_fields=["recovery_setup_completed"])

        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "username": "ready-user",
            "password": "StrongPassword123!",
        }
        mock_form_cls.return_value = form
        mock_authenticate.return_value = user

        request = self._request(
            "POST",
            "/login/",
            data={
                "username": "ready-user",
                "password": "StrongPassword123!",
            },
        )

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "core:home")

        self.assertNotIn(
            "backup_code_setup_pending",
            request.session,
        )

        mock_login.assert_called_once_with(
            request,
            user,
        )

        mock_reset.assert_called_once_with(
            action="login:username",
            identifier="ready-user",
        )

    @patch("user_app.views.authenticate", return_value=None)
    @patch("user_app.views.RateLimiter.reset")
    @patch("user_app.views.RateLimiter.check")
    @patch("user_app.views.RateLimiter.consume")
    @patch("user_app.views.LoginForm")
    @patch("user_app.views.render", side_effect=fake_render)
    def test_login_uses_lowercase_username_for_failure_counter(
        self,
        mock_render,
        mock_form_cls,
        mock_consume,
        mock_check,
        mock_reset,
        mock_authenticate,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "username": "AmIR",
            "password": "wrong",
        }
        mock_form_cls.return_value = form

        request = self._request(
            "POST",
            "/login/",
        )

        LoginView.as_view()(request)

        mock_check.assert_called_once()

        self.assertEqual(
            mock_check.call_args.kwargs["identifier"],
            "amir",
        )

    # ------------------------------------------------------------------
    # LogoutView
    # ------------------------------------------------------------------

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    @patch("user_app.views.logout")
    def test_logout_works_with_post(
        self,
        mock_logout,
        mock_redirect,
    ):
        request = self._authenticated_request(
            "POST",
            "/logout/",
        )

        response = LogoutView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "core:home")

        mock_logout.assert_called_once_with(request)
        mock_redirect.assert_called_once_with("core:home")

    def test_logout_does_not_implement_get(self):
        request = self._authenticated_request(
            "GET",
            "/logout/",
        )

        response = LogoutView.as_view()(request)

        self.assertEqual(response.status_code, 405)

    # ------------------------------------------------------------------
    # RegisterView
    # ------------------------------------------------------------------

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    def test_authenticated_user_is_redirected_from_register(
        self,
        mock_redirect,
    ):
        request = self._authenticated_request(
            "GET",
            "/register/",
        )

        response = RegisterView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "core:home")

        mock_redirect.assert_called_once_with("core:home")

    @patch("user_app.views.render", side_effect=fake_render)
    def test_anonymous_user_can_open_register_page(
        self,
        mock_render,
    ):
        request = self._request(
            "GET",
            "/register/",
        )

        response = RegisterView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.RegisterForm")
    def test_register_invalid_form_is_rendered(
        self,
        mock_form_cls,
        mock_render,
    ):
        form = MagicMock()
        form.is_valid.return_value = False
        mock_form_cls.return_value = form

        request = self._request(
            "POST",
            "/register/",
        )

        response = RegisterView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    @patch("user_app.views.login")
    @patch("user_app.views.UserService.register")
    @patch("user_app.views.RegisterForm")
    def test_register_creates_user_logs_in_and_redirects_to_backup_setup(
        self,
        mock_form_cls,
        mock_register,
        mock_login,
        mock_redirect,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "username": "new-user",
            "password": "StrongPassword123!",
        }
        mock_form_cls.return_value = form
        mock_register.return_value = self.user

        request = self._request(
            "POST",
            "/register/",
        )

        response = RegisterView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "user_app:backup_code_setup",
        )

        mock_register.assert_called_once_with(
            username="new-user",
            password="StrongPassword123!",
        )

        mock_login.assert_called_once_with(
            request,
            self.user,
        )

        mock_redirect.assert_called_once_with(
            "user_app:backup_code_setup"
        )

    # ------------------------------------------------------------------
    # BackupCodeSetupView
    # ------------------------------------------------------------------

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    def test_backup_setup_requires_authentication(
        self,
        mock_redirect,
    ):
        request = self._request(
            "GET",
            "/backup-codes/setup/",
        )

        response = BackupCodeSetupView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "user_app:login")

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.BackupCodeService.generate")
    def test_backup_setup_generates_and_stores_codes(
        self,
        mock_generate,
        mock_render,
    ):
        codes = [
            "CODE-111",
            "CODE-222",
        ]

        mock_generate.return_value = codes

        request = self._authenticated_request(
            "GET",
            "/backup-codes/setup/",
        )

        response = BackupCodeSetupView.as_view()(request)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            request.session["backup_codes"],
            codes,
        )

        self.assertTrue(
            request.session["backup_code_setup_pending"]
        )

        self.assertEqual(
            request.session.get_expiry_age(),
            600,
        )

        mock_generate.assert_called_once_with(
            user=self.user,
        )

        mock_render.assert_called_once()

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.BackupCodeService.generate")
    def test_backup_setup_reuses_codes_already_in_session(
        self,
        mock_generate,
        mock_render,
    ):
        codes = [
            "CODE-111",
            "CODE-222",
        ]

        request = self._authenticated_request(
            "GET",
            "/backup-codes/setup/",
        )

        request.session["backup_codes"] = codes

        response = BackupCodeSetupView.as_view()(request)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            request.session["backup_codes"],
            codes,
        )

        mock_generate.assert_not_called()
        mock_render.assert_called_once()

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    def test_completed_recovery_user_is_redirected_home_without_pending_setup(
        self,
        mock_redirect,
    ):
        self.user.recovery_setup_completed = True
        self.user.save(
            update_fields=["recovery_setup_completed"]
        )

        request = self._authenticated_request(
            "GET",
            "/backup-codes/setup/",
        )

        response = BackupCodeSetupView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "core:home")

        self.user.recovery_setup_completed = False
        self.user.save(
            update_fields=["recovery_setup_completed"]
        )

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    def test_completed_recovery_user_can_enter_setup_when_pending(
        self,
        mock_redirect,
    ):
        self.user.recovery_setup_completed = True
        self.user.save(
            update_fields=["recovery_setup_completed"]
        )

        request = self._authenticated_request(
            "GET",
            "/backup-codes/setup/",
        )

        request.session["backup_code_setup_pending"] = True

        with patch(
            "user_app.views.render",
            side_effect=fake_render,
        ), patch(
            "user_app.views.BackupCodeService.generate",
            return_value=["A", "B"],
        ):
            response = BackupCodeSetupView.as_view()(request)

        self.assertEqual(response.status_code, 200)

        self.user.recovery_setup_completed = False
        self.user.save(
            update_fields=["recovery_setup_completed"]
        )

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    def test_backup_setup_post_requires_authentication(
        self,
        mock_redirect,
    ):
        request = self._request(
            "POST",
            "/backup-codes/setup/",
        )

        response = BackupCodeSetupView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "user_app:login")

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.BackupCodeConfirmationForm")
    def test_backup_setup_invalid_confirmation_renders_existing_codes(
        self,
        mock_form_cls,
        mock_render,
    ):
        form = MagicMock()
        form.is_valid.return_value = False
        mock_form_cls.return_value = form

        request = self._authenticated_request(
            "POST",
            "/backup-codes/setup/",
        )

        codes = [
            "CODE-111",
            "CODE-222",
        ]

        request.session["backup_codes"] = codes

        response = BackupCodeSetupView.as_view()(request)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            request.session["backup_codes"],
            codes,
        )

        self.assertEqual(
            request.session.get_expiry_age(),
            600,
        )

        mock_render.assert_called_once()

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    @patch("user_app.views.UserService.mark_recovery_setup_completed")
    @patch("user_app.views.BackupCodeConfirmationForm")
    def test_backup_code_confirmation_removes_plaintext_codes_from_session(
            self,
            mock_form_cls,
            mock_mark_setup,
            mock_redirect,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        mock_form_cls.return_value = form

        request = self._authenticated_request(
            "POST",
            "/backup-codes/setup/",
        )

        request.session["backup_codes"] = [
            "CODE-111",
            "CODE-222",
        ]

        request.session["backup_code_setup_pending"] = True
        request.session.set_expiry(600)

        response = BackupCodeSetupView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "core:home")

        # Sensitive plaintext backup codes must be removed.
        self.assertNotIn(
            "backup_codes",
            request.session,
        )

        # Setup-pending state must also be removed.
        self.assertNotIn(
            "backup_code_setup_pending",
            request.session,
        )

        # set_expiry(None) restores Django's default session lifetime.
        self.assertEqual(
            request.session.get_expiry_age(),
            settings.SESSION_COOKIE_AGE,
        )

        mock_mark_setup.assert_called_once_with(
            user=self.user,
        )

        mock_redirect.assert_called_once_with(
            "core:home",
        )

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    @patch("user_app.views.BackupCodeConfirmationForm")
    def test_backup_code_confirmation_without_codes_redirects_to_setup(
        self,
        mock_form_cls,
        mock_redirect,
    ):
        form = MagicMock()
        form.is_valid.return_value = False
        mock_form_cls.return_value = form

        request = self._authenticated_request(
            "POST",
            "/backup-codes/setup/",
        )

        response = BackupCodeSetupView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "user_app:backup_code_setup",
        )

    # ------------------------------------------------------------------
    # BackupCodeRecoveryView
    # ------------------------------------------------------------------

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    def test_authenticated_user_is_redirected_from_recovery(
        self,
        mock_redirect,
    ):
        request = self._authenticated_request(
            "GET",
            "/recover/",
        )

        response = BackupCodeRecoveryView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "core:home")

    @patch("user_app.views.render", side_effect=fake_render)
    def test_anonymous_user_can_open_recovery_page(
        self,
        mock_render,
    ):
        request = self._request(
            "GET",
            "/recover/",
        )

        response = BackupCodeRecoveryView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.BackupCodeVerificationForm")
    def test_recovery_invalid_form_is_rendered(
        self,
        mock_form_cls,
        mock_render,
    ):
        form = MagicMock()
        form.is_valid.return_value = False
        mock_form_cls.return_value = form

        request = self._request(
            "POST",
            "/recover/",
        )

        response = BackupCodeRecoveryView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.BackupCodeVerificationForm")
    @patch("user_app.views.RateLimiter.check")
    @patch("user_app.views.RateLimiter.consume")
    def test_recovery_rate_limit_exceeded_renders_form_error(
        self,
        mock_consume,
        mock_check,
        mock_form_cls,
        mock_render,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "username": "amir",
            "code": "CODE-111",
        }
        mock_form_cls.return_value = form

        mock_consume.side_effect = RateLimitExceeded

        request = self._request(
            "POST",
            "/recover/",
        )

        response = BackupCodeRecoveryView.as_view()(request)

        self.assertEqual(response.status_code, 200)

        form.add_error.assert_called_once_with(
            None,
            "Too many recovery attempts. Please try again later.",
        )

        mock_check.assert_not_called()
        mock_render.assert_called_once()

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.BackupCodeVerificationForm")
    @patch("user_app.views.UserSelector.get_by_username", return_value=None)
    @patch("user_app.views.RateLimiter.record_failure")
    @patch("user_app.views.RateLimiter.check")
    @patch("user_app.views.RateLimiter.consume")
    def test_recovery_unknown_username_does_not_reveal_user_existence(
        self,
        mock_consume,
        mock_check,
        mock_record_failure,
        mock_get_by_username,
        mock_form_cls,
        mock_render,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "username": "UnknownUser",
            "code": "CODE-111",
        }
        mock_form_cls.return_value = form

        request = self._request(
            "POST",
            "/recover/",
        )

        response = BackupCodeRecoveryView.as_view()(request)

        self.assertEqual(response.status_code, 200)

        form.add_error.assert_called_once_with(
            None,
            "Invalid recovery credentials.",
        )

        mock_record_failure.assert_called_once()

        self.assertEqual(
            mock_record_failure.call_args.kwargs["identifier"],
            "unknownuser",
        )

        mock_render.assert_called_once()

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.BackupCodeVerificationForm")
    @patch("user_app.views.BackupCodeService.verify", return_value=False)
    @patch("user_app.views.UserSelector.get_by_username")
    @patch("user_app.views.RateLimiter.record_failure")
    @patch("user_app.views.RateLimiter.check")
    @patch("user_app.views.RateLimiter.consume")
    def test_recovery_invalid_backup_code_records_failure(
        self,
        mock_consume,
        mock_check,
        mock_record_failure,
        mock_get_by_username,
        mock_verify,
        mock_form_cls,
        mock_render,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "username": "AmIr",
            "code": "WRONG-CODE",
        }
        mock_form_cls.return_value = form

        mock_get_by_username.return_value = self.user

        request = self._request(
            "POST",
            "/recover/",
        )

        response = BackupCodeRecoveryView.as_view()(request)

        self.assertEqual(response.status_code, 200)

        mock_verify.assert_called_once_with(
            user=self.user,
            code="WRONG-CODE",
        )

        mock_record_failure.assert_called_once()

        self.assertEqual(
            mock_record_failure.call_args.kwargs["identifier"],
            "amir",
        )

        form.add_error.assert_called_once_with(
            None,
            "Invalid recovery credentials.",
        )

        mock_render.assert_called_once()

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    @patch("user_app.views.BackupCodeService.verify", return_value=True)
    @patch("user_app.views.UserSelector.get_by_username")
    @patch("user_app.views.RateLimiter.reset")
    @patch("user_app.views.RateLimiter.check")
    @patch("user_app.views.RateLimiter.consume")
    @patch("user_app.views.BackupCodeVerificationForm")
    def test_recovery_success_creates_short_lived_recovery_session(
        self,
        mock_form_cls,
        mock_consume,
        mock_check,
        mock_reset,
        mock_get_by_username,
        mock_verify,
        mock_redirect,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "username": "AmIr",
            "code": "VALID-CODE",
        }
        mock_form_cls.return_value = form

        mock_get_by_username.return_value = self.user

        request = self._request(
            "POST",
            "/recover/",
        )

        old_session_key = request.session.session_key

        response = BackupCodeRecoveryView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "user_app:reset-master-password",
        )

        self.assertNotEqual(
            request.session.session_key,
            old_session_key,
        )

        self.assertEqual(
            request.session["recovery_user_id"],
            self.user.pk,
        )

        self.assertEqual(
            request.session.get_expiry_age(),
            600,
        )

        mock_reset.assert_called_once_with(
            action="recovery:username",
            identifier="amir",
        )

        mock_redirect.assert_called_once_with(
            "user_app:reset-master-password"
        )

    # ------------------------------------------------------------------
    # ResetMasterPasswordView
    # ------------------------------------------------------------------

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    def test_reset_password_requires_recovery_session_on_get(
        self,
        mock_redirect,
    ):
        request = self._request(
            "GET",
            "/reset-master-password/",
        )

        response = ResetMasterPasswordView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "user_app:recover")

    @patch("user_app.views.render", side_effect=fake_render)
    def test_reset_password_get_renders_form_with_recovery_session(
        self,
        mock_render,
    ):
        request = self._request(
            "GET",
            "/reset-master-password/",
        )

        request.session["recovery_user_id"] = self.user.pk

        response = ResetMasterPasswordView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.ResetPasswordForm")
    def test_reset_password_invalid_form_is_rendered(
        self,
        mock_form_cls,
        mock_render,
    ):
        form = MagicMock()
        form.is_valid.return_value = False
        mock_form_cls.return_value = form

        request = self._request(
            "POST",
            "/reset-master-password/",
        )

        request.session["recovery_user_id"] = self.user.pk

        response = ResetMasterPasswordView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    @patch("user_app.views.login")
    @patch("user_app.views.UserService.change_password")
    @patch("user_app.views.UserSelector.get_by_id")
    @patch("user_app.views.ResetPasswordForm")
    def test_reset_password_success_changes_password_flushes_session_and_reauthenticates(
        self,
        mock_form_cls,
        mock_get_by_id,
        mock_change_password,
        mock_login,
        mock_redirect,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "password": "NewStrongPassword123!",
        }
        mock_form_cls.return_value = form

        mock_get_by_id.return_value = self.user

        request = self._request(
            "POST",
            "/reset-master-password/",
        )

        request.session["recovery_user_id"] = self.user.pk
        request.session["some_old_value"] = "must-disappear"

        response = ResetMasterPasswordView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "user_app:backup_code_setup",
        )

        self.assertNotIn(
            "recovery_user_id",
            request.session,
        )

        self.assertNotIn(
            "some_old_value",
            request.session,
        )

        self.assertTrue(
            request.session["backup_code_setup_pending"]
        )

        self.assertEqual(
            request.session.get_expiry_age(),
            600,
        )

        mock_change_password.assert_called_once_with(
            user=self.user,
            new_password="NewStrongPassword123!",
        )

        mock_login.assert_called_once_with(
            request,
            self.user,
        )

        mock_redirect.assert_called_once_with(
            "user_app:backup_code_setup"
        )

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    @patch("user_app.views.UserSelector.get_by_id", return_value=None)
    @patch("user_app.views.ResetPasswordForm")
    def test_reset_password_missing_user_flushes_session_and_redirects_to_recovery(
        self,
        mock_form_cls,
        mock_get_by_id,
        mock_redirect,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "password": "NewStrongPassword123!",
        }
        mock_form_cls.return_value = form

        request = self._request(
            "POST",
            "/reset-master-password/",
        )

        request.session["recovery_user_id"] = 999999
        request.session["temporary"] = "value"

        response = ResetMasterPasswordView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "user_app:recover")

        self.assertNotIn(
            "recovery_user_id",
            request.session,
        )

        self.assertNotIn(
            "temporary",
            request.session,
        )

        mock_redirect.assert_called_once_with(
            "user_app:recover"
        )

    # ------------------------------------------------------------------
    # RegenerateBackupCodesView
    # ------------------------------------------------------------------

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    def test_regenerate_backup_codes_requires_authentication(
        self,
        mock_redirect,
    ):
        request = self._request(
            "GET",
            "/backup-codes/regenerate/",
        )

        response = RegenerateBackupCodesView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "user_app:login")

    @patch("user_app.views.render", side_effect=fake_render)
    def test_regenerate_backup_codes_get_renders_form_for_authenticated_user(
        self,
        mock_render,
    ):
        request = self._authenticated_request(
            "GET",
            "/backup-codes/regenerate/",
        )

        response = RegenerateBackupCodesView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()

    @patch("user_app.views.render", side_effect=fake_render)
    @patch("user_app.views.RegenerateBackupCodesForm")
    def test_regenerate_backup_codes_invalid_form_is_rendered(
        self,
        mock_form_cls,
        mock_render,
    ):
        form = MagicMock()
        form.is_valid.return_value = False
        mock_form_cls.return_value = form

        request = self._authenticated_request(
            "POST",
            "/backup-codes/regenerate/",
        )

        response = RegenerateBackupCodesView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()

    @patch("user_app.views.redirect", side_effect=fake_redirect)
    @patch("user_app.views.BackupCodeService.regenerate")
    @patch("user_app.views.RegenerateBackupCodesForm")
    def test_regenerate_backup_codes_success_stores_codes_and_redirects(
        self,
        mock_form_cls,
        mock_regenerate,
        mock_redirect,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        mock_form_cls.return_value = form

        codes = [
            "NEW-111",
            "NEW-222",
        ]

        mock_regenerate.return_value = codes

        request = self._authenticated_request(
            "POST",
            "/backup-codes/regenerate/",
        )

        response = RegenerateBackupCodesView.as_view()(request)

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            response.url,
            "user_app:backup_code_setup",
        )

        self.assertEqual(
            request.session["backup_codes"],
            codes,
        )

        mock_regenerate.assert_called_once_with(
            user=self.user,
        )

        mock_redirect.assert_called_once_with(
            "user_app:backup_code_setup"
        )

    @patch("user_app.views.render", side_effect=fake_render)
    @patch(
        "user_app.views.BackupCodeService.regenerate",
        side_effect=CooldownActive,
    )
    @patch("user_app.views.RegenerateBackupCodesForm")
    def test_regenerate_backup_codes_cooldown_is_rendered_as_form_error(
        self,
        mock_form_cls,
        mock_regenerate,
        mock_render,
    ):
        form = MagicMock()
        form.is_valid.return_value = True
        mock_form_cls.return_value = form

        request = self._authenticated_request(
            "POST",
            "/backup-codes/regenerate/",
        )

        response = RegenerateBackupCodesView.as_view()(request)

        self.assertEqual(response.status_code, 200)

        form.add_error.assert_called_once_with(
            None,
            "Backup codes were recently regenerated, Please try again later.",
        )

        mock_render.assert_called_once()