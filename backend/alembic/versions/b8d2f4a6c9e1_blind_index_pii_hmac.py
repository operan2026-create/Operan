"""Replace SHA-256 PII hashes with keyed HMAC blind indexes

Revision ID: b8d2f4a6c9e1
Revises: f1b3c5d7e9a2
Create Date: 2026-10-27 10:00:00.000000

The old lookup hashes were a plain SHA-256 of e-mail, CPF, RG and CNPJ. Those
values have low entropy, so an attacker with database access could recover them
with an offline dictionary. This migration recomputes every lookup hash with a
keyed HMAC-SHA256 using PII_INDEX_KEY, which must be provided outside the
database.

The plaintext is read from the encrypted columns, so CRYPTO_KEY must be
available while this migration runs. The operation is transactional on
PostgreSQL: any failure rolls the whole migration back.
"""

import hashlib
import hmac
import logging
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8d2f4a6c9e1"
down_revision: Union[str, Sequence[str], None] = "f1b3c5d7e9a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DECRYPT_SENTINEL = "[Encrypted Data]"
logger = logging.getLogger("alembic.runtime.migration")


def _pii_key() -> bytes:
    key = (os.environ.get("PII_INDEX_KEY") or "").strip()
    if not key:
        # Fall back to the application settings, which load .env.
        from app.core.config import settings

        key = settings.PII_INDEX_KEY.strip()
    if not key:
        raise RuntimeError(
            "PII_INDEX_KEY is required to run this migration. Configure it in the "
            "environment (never in the database) before upgrading."
        )
    return key.encode("utf-8")


def _hmac(key: bytes, value: str) -> str:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _email_index(key: bytes, email: str) -> str:
    return _hmac(key, email.strip().lower())


def _cpf_index(key: bytes, cpf: str) -> str:
    return _hmac(key, "".join(filter(str.isdigit, cpf)))


def _cnpj_index(key: bytes, cnpj: str) -> str:
    return _hmac(key, "".join(filter(str.isdigit, cnpj)))


def _rg_index(key: bytes, rg: str) -> str:
    return _hmac(key, rg.strip().lower())


def _decrypt(value: str, table: str, column: str, row_id) -> str:
    from app.security.encryption import crypto_manager

    plaintext = crypto_manager.decrypt_data(value)
    if plaintext == _DECRYPT_SENTINEL:
        raise RuntimeError(
            f"Could not decrypt {table}.{column} for row {row_id}. "
            "Check CRYPTO_KEY before running this migration."
        )
    return plaintext


def _recompute(
    bind,
    *,
    table: str,
    select_columns: str,
    updates,
    key: bytes,
    tolerate_decrypt_errors: bool = False,
) -> None:
    """Iterates rows and updates one or more hash columns.

    ``updates`` is a list of (hash_column, plaintext_column, normaliser) tuples.
    When ``tolerate_decrypt_errors`` is true, an undecryptable value clears the
    hash (removing the legacy weak hash) and logs a warning instead of aborting.
    This is only used for hashes that are not part of any lookup today.
    """
    rows = bind.execute(
        sa.text(f"SELECT id, {select_columns} FROM {table}")
    ).mappings()
    for row in rows:
        values = {}
        for hash_column, plaintext_column, normaliser in updates:
            raw = row[plaintext_column]
            if raw is None or raw == "":
                values[hash_column] = None
                continue
            try:
                plaintext = _decrypt(raw, table, plaintext_column, row["id"])
            except RuntimeError:
                if not tolerate_decrypt_errors:
                    raise
                logger.warning(
                    "Could not decrypt %s.%s for row %s; clearing %s because it "
                    "is not used for lookups. Re-encrypt this field if needed.",
                    table,
                    plaintext_column,
                    row["id"],
                    hash_column,
                )
                values[hash_column] = None
                continue
            values[hash_column] = normaliser(key, plaintext) if plaintext else None
        assignments = ", ".join(f"{name} = :{name}" for name in values)
        bind.execute(
            sa.text(f"UPDATE {table} SET {assignments} WHERE id = :row_id"),
            {**values, "row_id": row["id"]},
        )


def upgrade() -> None:
    bind = op.get_bind()
    key = _pii_key()

    _recompute(
        bind,
        table="users",
        select_columns="email_encrypted",
        updates=[("email_hash", "email_encrypted", _email_index)],
        key=key,
    )
    _recompute(
        bind,
        table="invitations",
        select_columns="email_encrypted",
        updates=[("email_hash", "email_encrypted", _email_index)],
        key=key,
    )
    _recompute(
        bind,
        table="person_profiles",
        select_columns="cpf_encrypted",
        updates=[("cpf_hash", "cpf_encrypted", _cpf_index)],
        key=key,
    )
    _recompute(
        bind,
        table="person_profiles",
        select_columns="rg_encrypted",
        updates=[("rg_hash", "rg_encrypted", _rg_index)],
        key=key,
        tolerate_decrypt_errors=True,
    )
    _recompute(
        bind,
        table="professionals",
        select_columns="cpf_encrypted",
        updates=[("cpf_hash", "cpf_encrypted", _cpf_index)],
        key=key,
    )
    _recompute(
        bind,
        table="organizations",
        select_columns="cnpj_encrypted",
        updates=[("cnpj_hash", "cnpj_encrypted", _cnpj_index)],
        key=key,
        tolerate_decrypt_errors=True,
    )
    _recompute(
        bind,
        table="participant_bank_accounts",
        select_columns="holder_cpf",
        updates=[("holder_cpf_hash", "holder_cpf", _cpf_index)],
        key=key,
    )
    _recompute(
        bind,
        table="participant_family_members",
        select_columns="cpf",
        updates=[("cpf_hash", "cpf", _cpf_index)],
        key=key,
    )


def _legacy_sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _legacy_email(value: str) -> str:
    return _legacy_sha256(value.lower())


def _legacy_cpf(value: str) -> str:
    return _legacy_sha256("".join(filter(str.isdigit, value)))


def _legacy_cnpj(value: str) -> str:
    return _legacy_sha256("".join(filter(str.isdigit, value)))


def _legacy_rg(value: str) -> str:
    return _legacy_sha256(value.lower())


def _legacy_raw(value: str) -> str:
    return _legacy_sha256(value)


def downgrade() -> None:
    bind = op.get_bind()

    _recompute(
        bind,
        table="users",
        select_columns="email_encrypted",
        updates=[("email_hash", "email_encrypted", lambda _k, v: _legacy_email(v))],
        key=b"",
    )
    _recompute(
        bind,
        table="invitations",
        select_columns="email_encrypted",
        updates=[("email_hash", "email_encrypted", lambda _k, v: _legacy_email(v))],
        key=b"",
    )
    _recompute(
        bind,
        table="person_profiles",
        select_columns="cpf_encrypted",
        updates=[("cpf_hash", "cpf_encrypted", lambda _k, v: _legacy_cpf(v))],
        key=b"",
    )
    _recompute(
        bind,
        table="person_profiles",
        select_columns="rg_encrypted",
        updates=[("rg_hash", "rg_encrypted", lambda _k, v: _legacy_rg(v))],
        key=b"",
        tolerate_decrypt_errors=True,
    )
    _recompute(
        bind,
        table="professionals",
        select_columns="cpf_encrypted",
        updates=[("cpf_hash", "cpf_encrypted", lambda _k, v: _legacy_cpf(v))],
        key=b"",
    )
    _recompute(
        bind,
        table="organizations",
        select_columns="cnpj_encrypted",
        updates=[("cnpj_hash", "cnpj_encrypted", lambda _k, v: _legacy_cnpj(v))],
        key=b"",
        tolerate_decrypt_errors=True,
    )
    _recompute(
        bind,
        table="participant_bank_accounts",
        select_columns="holder_cpf",
        updates=[("holder_cpf_hash", "holder_cpf", lambda _k, v: _legacy_raw(v))],
        key=b"",
    )
    _recompute(
        bind,
        table="participant_family_members",
        select_columns="cpf",
        updates=[("cpf_hash", "cpf", lambda _k, v: _legacy_raw(v))],
        key=b"",
    )
