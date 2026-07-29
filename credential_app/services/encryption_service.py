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
        Encrypt a plain text password.
        """
        encrypted = cls._cipher.encrypt(
            plaintext.encode() # Formating plain text into bytes for encryption
        )
        return encrypted.decode() # Formating bytes into characters that encrypted

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """
        Decrypt an encrypted password.
        """
        decrypted = cls._cipher.decrypt(
            ciphertext.encode()
        )
        return decrypted.decode() 