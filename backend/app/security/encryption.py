import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64

class CryptoManager:
    """
    Base Envelope Encryption manager for application-level data encryption.
    In a real scenario, the KEK (Key Encryption Key) should be retrieved from a KMS or Vault.
    Here we mock the KEK retrieval using an environment variable or a locally generated key.
    """
    
    def __init__(self, kek_base64: str = None):
        # MOCK: Fallback to a random key if not provided (NOT for production!)
        if not kek_base64:
            kek_base64 = base64.b64encode(AESGCM.generate_key(bit_length=256)).decode('utf-8')
        self._kek = base64.b64decode(kek_base64)
        self.aesgcm = AESGCM(self._kek)

    def encrypt_data(self, data: str) -> str:
        """
        Encrypts sensitive data (e.g. CPF, Phone) before saving to the database.
        Returns base64 encoded ciphertext including the nonce.
        """
        nonce = os.urandom(12)
        encoded_data = data.encode('utf-8')
        ciphertext = self.aesgcm.encrypt(nonce, encoded_data, None)
        # Store nonce prepended to ciphertext, then base64 encode
        return base64.b64encode(nonce + ciphertext).decode('utf-8')

    def decrypt_data(self, encrypted_data_b64: str) -> str:
        """
        Decrypts sensitive data retrieved from the database.
        """
        try:
            encrypted_data = base64.b64decode(encrypted_data_b64)
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            decrypted_data = self.aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_data.decode('utf-8')
        except Exception:
            return "[Encrypted Data]"

from app.core.config import settings
crypto_manager = CryptoManager(settings.CRYPTO_KEY)
