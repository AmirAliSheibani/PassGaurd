class DuplicateCredential(Exception):
    """Raised when a vault already contains a credential with this service name."""


class VaultOwnershipMismatch(ValueError):
    """Raised when a credential is moved to another user's vault."""


class CategoryOwnershipMismatch(ValueError):
    """Raised when a credential is assigned a category owned by another user."""
