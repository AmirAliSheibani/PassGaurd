from cryptography.fernet import Fernet
from django.conf import settings

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
        Encrypts plain text password.
        """
        encrypted = cls._cipher.encrypt(
            plaintext.encode() # Formating plain text into bytes for encryption
        )
        return encrypted.decode() # Formating bytes into characters that encrypted


