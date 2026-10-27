"""Encrypt participant PII and add encrypted profile avatar

Revision ID: e6a2b8c4d913
Revises: d4f7a9c2e6b8
Create Date: 2026-10-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.security.encryption import crypto_manager

revision: str = "e6a2b8c4d913"
down_revision: Union[str, Sequence[str], None] = "d4f7a9c2e6b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROFILE_TEXT_FIELDS = (
    "full_name",
    "social_name",
    "gender",
    "city",
    "state",
    "zip_code",
    "address_street",
    "address_number",
    "address_complement",
    "address_neighborhood",
    "emergency_contact_name",
    "bio",
)
PROFESSIONAL_TEXT_FIELDS = ("full_name", "city", "state")


def _encrypt(value):
    if value is None:
        return None
    return crypto_manager.encrypt_data(str(value))


def _decrypt(value):
    if value is None:
        return None
    return crypto_manager.decrypt_data(str(value))


def _encrypt_rows(table: str, fields: tuple[str, ...], extra=()) -> None:
    bind = op.get_bind()
    columns = ", ".join(("id",) + fields + extra)
    rows = bind.execute(sa.text(f"SELECT {columns} FROM {table}")).mappings().all()
    assignments = ", ".join(f"{field}=:{field}" for field in fields + extra)
    updates = []
    for row in rows:
        values = {"id": row["id"]}
        for field in fields:
            values[field] = _encrypt(row[field])
        for field in extra:
            values[field] = _encrypt(row[field])
        updates.append(values)
    for values in updates:
        bind.execute(
            sa.text(f"UPDATE {table} SET {assignments} WHERE id=:id"), values
        )


def _decrypt_rows(table: str, fields: tuple[str, ...], extra=()) -> None:
    bind = op.get_bind()
    columns = ", ".join(("id",) + fields + extra)
    rows = bind.execute(sa.text(f"SELECT {columns} FROM {table}")).mappings().all()
    assignments = ", ".join(f"{field}=:{field}" for field in fields + extra)
    updates = []
    for row in rows:
        values = {"id": row["id"]}
        for field in fields:
            values[field] = _decrypt(row[field])
        for field in extra:
            values[field] = _decrypt(row[field])
        updates.append(values)
    for values in updates:
        bind.execute(
            sa.text(f"UPDATE {table} SET {assignments} WHERE id=:id"), values
        )


def upgrade() -> None:
    for column in PROFILE_TEXT_FIELDS:
        op.alter_column(
            "person_profiles",
            column,
            existing_type=sa.String(),
            type_=sa.Text(),
            existing_nullable=column in {"full_name", "city"},
        )
    op.alter_column(
        "person_profiles",
        "birth_date",
        existing_type=sa.Date(),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="birth_date::text",
    )
    op.add_column("person_profiles", sa.Column("avatar_data", sa.Text(), nullable=True))
    op.add_column(
        "person_profiles", sa.Column("avatar_mime_type", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "person_profiles", sa.Column("avatar_sha256", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "person_profiles",
        sa.Column("avatar_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_index(op.f("ix_person_profiles_city"), table_name="person_profiles")
    op.drop_index(op.f("ix_person_profiles_state"), table_name="person_profiles")
    _encrypt_rows(
        "person_profiles", PROFILE_TEXT_FIELDS, extra=("birth_date",)
    )

    for column in PROFESSIONAL_TEXT_FIELDS:
        op.alter_column(
            "professionals",
            column,
            existing_type=sa.String(),
            type_=sa.Text(),
            existing_nullable=False,
        )
    op.drop_index(op.f("ix_professionals_city"), table_name="professionals")
    op.drop_index(op.f("ix_professionals_state"), table_name="professionals")
    _encrypt_rows("professionals", PROFESSIONAL_TEXT_FIELDS)

    op.alter_column(
        "documents",
        "file_name",
        existing_type=sa.String(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    _encrypt_rows("documents", ("file_name",))


def downgrade() -> None:
    _decrypt_rows("documents", ("file_name",))
    op.alter_column(
        "documents",
        "file_name",
        existing_type=sa.Text(),
        type_=sa.String(),
        existing_nullable=False,
    )

    _decrypt_rows("professionals", PROFESSIONAL_TEXT_FIELDS)
    op.create_index(
        op.f("ix_professionals_city"), "professionals", ["city"], unique=False
    )
    op.create_index(
        op.f("ix_professionals_state"), "professionals", ["state"], unique=False
    )
    op.alter_column(
        "professionals",
        "state",
        existing_type=sa.Text(),
        type_=sa.String(length=2),
        existing_nullable=False,
    )
    for column in ("full_name", "city"):
        op.alter_column(
            "professionals",
            column,
            existing_type=sa.Text(),
            type_=sa.String(),
            existing_nullable=False,
        )

    _decrypt_rows(
        "person_profiles", PROFILE_TEXT_FIELDS, extra=("birth_date",)
    )
    op.drop_column("person_profiles", "avatar_updated_at")
    op.drop_column("person_profiles", "avatar_sha256")
    op.drop_column("person_profiles", "avatar_mime_type")
    op.drop_column("person_profiles", "avatar_data")
    op.alter_column(
        "person_profiles",
        "birth_date",
        existing_type=sa.Text(),
        type_=sa.Date(),
        existing_nullable=True,
        postgresql_using="birth_date::date",
    )
    op.alter_column(
        "person_profiles",
        "state",
        existing_type=sa.Text(),
        type_=sa.String(length=2),
        existing_nullable=False,
    )
    op.alter_column(
        "person_profiles",
        "zip_code",
        existing_type=sa.Text(),
        type_=sa.String(length=10),
        existing_nullable=True,
    )
    for column in ("full_name", "social_name", "gender", "city", "address_street",
                   "address_number", "address_complement", "address_neighborhood",
                   "emergency_contact_name", "bio"):
        op.alter_column(
            "person_profiles",
            column,
            existing_type=sa.Text(),
            type_=sa.String(),
            existing_nullable=column in {"full_name", "city"},
        )
    op.create_index(
        op.f("ix_person_profiles_city"), "person_profiles", ["city"], unique=False
    )
    op.create_index(
        op.f("ix_person_profiles_state"), "person_profiles", ["state"], unique=False
    )
