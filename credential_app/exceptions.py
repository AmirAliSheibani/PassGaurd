class DuplicateCredential(Exception):
    """Raised when a credential name conflicts within a target vault."""


class VaultOwnershipMismatch(ValueError):
    """Raised when a credential is moved to another user's vault."""


class InvalidCredentialSelection(ValueError):
    """Raised when a bulk operation receives an empty or invalid selection."""


class CredentialOwnershipMismatch(InvalidCredentialSelection):
    """Raised when one or more selected credentials are not owned by the user."""

