class LoginRateLimitPolicy:
    IP_LIMIT = 20
    IP_WINDOW = 60

    USERNAME_FAILURE_LIMIT = 5
    USERNAME_FAILURE_WINDOW = 300


class RecoveryRateLimitPolicy:
    IP_LIMIT = 10
    IP_WINDOW = 300

    USERNAME_FAILURE_LIMIT = 5
    USERNAME_FAILURE_WINDOW = 300


class BackupCodeRegenerationPolicy:
    COOLDOWN_SECONDS = 300