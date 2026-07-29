from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from .exceptions import EncryptionError

# Use this generated key for your encryptions, add it on your .env
# key = Fernet.generate_key().decode()
# print(key)

class EncryptionService:
    """
    Handles symmetric encryption and decryption
    of credential passwords using Fernet.
    """

    _cipher = Fernet(settings.FERNET_KEY.encode())

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """
        Encrypt a plain text password.
        """
        try:
            encrypted = cls._cipher.encrypt(
                plaintext.encode() # Formating plain text into bytes for encryption
            )
            return encrypted.decode() # Formating bytes into characters that encrypted
        except InvalidToken as exc:
            raise EncryptionError(
                "Unable to encrypt credential."
            )

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """
        Decrypt an encrypted password.
        """
        try:
            decrypted = cls._cipher.decrypt(
                ciphertext.encode()
            )
            return decrypted.decode()
        except InvalidToken as exc:
            raise EncryptionError(
                "Unable to decrypt credential."
            ) from exc

