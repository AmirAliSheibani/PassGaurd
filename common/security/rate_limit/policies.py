class LoginRateLimitPolicy:
    IP_LIMIT = 20
    IP_WINDOW = 60

    USERNAME_LIMIT = 5
    USERNAME_WINDOW = 300


class RecoveryRateLimitPolicy:
    IP_LIMIT = 20
    IP_WINDOW = 300

    USERNAME_LIMIT = 5
    USERNAME_WINDOW = 300


class BackupCodeRegenerationPolicy:
    COOLDOWN = 300

