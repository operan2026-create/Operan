"""Deterministic blind indexes for PII.

The previous implementation used a plain SHA-256 of the normalised value, which
is vulnerable to offline dictionary and rainbow-table attacks because CPFs,
e-mails and CNPJs have low entropy. A keyed HMAC (SHA-256) closes that gap while
still allowing exact-match lookups on encrypted data.
"""

import hashlib
import hmac

from app.core.config import settings


class PIIIndexKeyMissing(RuntimeError):
    """Raised when the dedicated PII index key is not configured."""


def _key() -> bytes:
    key = (settings.PII_INDEX_KEY or "").strip()
    if not key:
        raise PIIIndexKeyMissing(
            "PII_INDEX_KEY is required to compute PII blind indexes."
        )
    return key.encode("utf-8")


def blind_index(value: str) -> str:
    """Returns a keyed HMAC-SHA256 hex digest for the given normalised value."""
    return hmac.new(_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def normalize_cpf(cpf: str) -> str:
    return "".join(filter(str.isdigit, cpf or ""))


def normalize_cnpj(cnpj: str) -> str:
    return "".join(filter(str.isdigit, cnpj or ""))


def normalize_rg(rg: str) -> str:
    return (rg or "").strip().lower()


def email_index(email: str) -> str:
    return blind_index(normalize_email(email))


def cpf_index(cpf: str) -> str:
    return blind_index(normalize_cpf(cpf))


def cnpj_index(cnpj: str) -> str:
    return blind_index(normalize_cnpj(cnpj))


def rg_index(rg: str) -> str:
    return blind_index(normalize_rg(rg))
