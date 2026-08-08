class BackupCodeAlreadyUsedError(Exception):
    """
    Raised when a backup code already exists.
    """
    pass


class InvalidBackupCodeError(Exception):
    """
    Raised when a backup code is invalid.
    """
    pass


class RecoverySetupAlreadyCompletedError(Exception):
    """
    Raised when a recovery setup already completed.
    """
    pass