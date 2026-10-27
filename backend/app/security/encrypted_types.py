from datetime import date
from typing import Optional

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.security.encryption import crypto_manager


class EncryptedString(TypeDecorator):
    """Transparent AES-GCM encryption for text columns.

    The database only stores ciphertext. Application code reads and writes the
    original text value, which keeps the service layer free of manual
    encryption/decryption calls.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, str):
            value = str(value)
        return crypto_manager.encrypt_data(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return crypto_manager.decrypt_data(value)


class EncryptedText(EncryptedString):
    pass


class EncryptedDate(TypeDecorator):
    """Stores a date as encrypted ISO text and returns a date object."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Optional[date], dialect):
        if value is None:
            return None
        if isinstance(value, str):
            value = date.fromisoformat(value)
        return crypto_manager.encrypt_data(value.isoformat())

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        decrypted = crypto_manager.decrypt_data(value)
        try:
            return date.fromisoformat(decrypted)
        except ValueError:
            return None
