from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

from common.security.encryption.exceptions import EncryptionError


class EncryptionService:
    """Encrypt and decrypt credential passwords with the configured Fernet key."""

    _cipher = Fernet(settings.FERNET_KEY.encode("ascii"))

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        if not isinstance(plaintext, str):
            raise TypeError("Plaintext must be a string.")
        try:
            return cls._cipher.encrypt(plaintext.encode("utf-8")).decode("ascii")
        except (TypeError, ValueError, UnicodeError) as exc:
            raise EncryptionError("Unable to encrypt credential.") from exc

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        if not isinstance(ciphertext, str):
            raise EncryptionError("Unable to decrypt credential.")
        try:
            decrypted = cls._cipher.decrypt(ciphertext.encode("ascii"))
            return decrypted.decode("utf-8")
        except (InvalidToken, TypeError, ValueError, UnicodeError) as exc:
            raise EncryptionError("Unable to decrypt credential.") from exc
