from django.urls import path

from .views import (
    BackupCodeRecoveryView,
    BackupCodeSetupView,
    LoginView,
    LogoutView,
    RegisterView,
    RegenerateBackupCodesView,
    ResetMasterPasswordView,
)

app_name = "user_app"


urlpatterns = [
    # Authentication
    path("login/", LoginView.as_view(), name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout",
    ),
    path("register/", RegisterView.as_view(), name="register",
    ),

    # Account recovery
    path("recovery/", BackupCodeRecoveryView.as_view(), name="recovery",
    ),
    path("recovery/reset-password/", ResetMasterPasswordView.as_view(), name="reset_master_password",
    ),

    # Backup code management
    path("recovery/backup-codes/setup/", BackupCodeSetupView.as_view(), name="backup_code_setup",
    ),
    path("recovery/backup-codes/regenerate/", RegenerateBackupCodesView.as_view(), name="regenerate_backup_codes",
    ),
]
