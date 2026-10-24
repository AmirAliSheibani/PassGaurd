

class DuplicateCredential(Exception):
    """
    Raised when a credential already exists.
    """
    pass

class VaultOwnershipMismatch(ValueError):
    """
    Raised when a credential is moved to a vault
    owned by a different user.
    """