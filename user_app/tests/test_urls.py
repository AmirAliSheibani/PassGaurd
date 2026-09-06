from django.test import SimpleTestCase
from django.urls import resolve

from user_app.views import (
    BackupCodeRecoveryView,
    LoginView,
    LogoutView,
    RegisterView,
    RegenerateBackupCodesView,
    ResetMasterPasswordView,
    BackupCodeSetupView,
)


class UserURLTests(SimpleTestCase):

    def test_login_url(self):
        match = resolve("/login/")

        self.assertEqual(
            match.url_name,
            "login",
        )

        self.assertEqual(
            match.func.view_class,
            LoginView,
        )

    def test_logout_url(self):
        match = resolve("/logout/")

        self.assertEqual(
            match.url_name,
            "logout",
        )

        self.assertEqual(
            match.func.view_class,
            LogoutView,
        )

    def test_register_url(self):
        match = resolve("/register/")

        self.assertEqual(
            match.url_name,
            "register",
        )

        self.assertEqual(
            match.func.view_class,
            RegisterView,
        )

    def test_recovery_url(self):
        match = resolve("/recovery/")

        self.assertEqual(
            match.url_name,
            "recovery",
        )

        self.assertEqual(
            match.func.view_class,
            BackupCodeRecoveryView,
        )

    def test_reset_password_url(self):
        match = resolve(
            "/recovery/reset-password/"
        )

        self.assertEqual(
            match.url_name,
            "reset_master_password",
        )

        self.assertEqual(
            match.func.view_class,
            ResetMasterPasswordView,
        )

    def test_backup_code_setup_url(self):
        match = resolve(
            "/recovery/backup-codes/setup/"
        )

        self.assertEqual(
            match.url_name,
            "backup_code_setup",
        )

        self.assertEqual(
            match.func.view_class,
            BackupCodeSetupView,
        )

    def test_backup_code_regeneration_url(self):
        match = resolve(
            "/recovery/backup-codes/regenerate/"
        )

        self.assertEqual(
            match.url_name,
            "regenerate_backup_codes",
        )

        self.assertEqual(
            match.func.view_class,
            RegenerateBackupCodesView,
        )