class EncryptionError(Exception):
    """
    Raised when encryption or decryption fails.
    """
    pass


class DuplicateCredential(Exception):
    """
    Raised when a credential already exists.
    """
    pass