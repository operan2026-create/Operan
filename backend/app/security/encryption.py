import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64

class CryptoManager:
    """
    Base Envelope Encryption manager for application-level data encryption.
    In a real scenario, the KEK (Key Encryption Key) should be retrieved from a KMS or Vault.
    Here we mock the KEK retrieval using an environment variable or a locally generated key.
    """
    
    def __init__(self, kek_base64: str):
        # A chave deve vir de configuracao explicita. Nunca gerar uma chave
        # aleatoria implicitamente: isso tornaria dados existentes ilegiveis.
        if not kek_base64:
            raise ValueError("CRYPTO_KEY is required to initialise encryption.")
        self._kek = base64.b64decode(kek_base64)
        if len(self._kek) != 32:
            raise ValueError("CRYPTO_KEY must decode to exactly 32 bytes (AES-256).")
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

    def encrypt_bytes(self, data: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + self.aesgcm.encrypt(nonce, data, None)

    def decrypt_bytes(self, payload: bytes) -> bytes:
        nonce = payload[:12]
        return self.aesgcm.decrypt(nonce, payload[12:], None)

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
