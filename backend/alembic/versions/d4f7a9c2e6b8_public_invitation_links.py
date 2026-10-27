"""Add reusable public invitation links

Revision ID: d4f7a9c2e6b8
Revises: b2e4f6a8c1d3
Create Date: 2026-10-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4f7a9c2e6b8"
down_revision: Union[str, Sequence[str], None] = "b2e4f6a8c1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PUBLIC_INVITATION_STATUS = postgresql.ENUM(
    "ACTIVE", "REVOKED", "EXPIRED", name="publicinvitationstatus"
)
JOURNEY_TYPE = postgresql.ENUM("LOCATIONS", "PROFESSIONALS", name="journeytype")


def _column_enum(enum_type: postgresql.ENUM) -> postgresql.ENUM:
    return postgresql.ENUM(*enum_type.enums, name=enum_type.name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    PUBLIC_INVITATION_STATUS.create(bind, checkfirst=True)
    op.create_table(
        "public_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("token_encrypted", sa.String(), nullable=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("journey_type", _column_enum(JOURNEY_TYPE), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            _column_enum(PUBLIC_INVITATION_STATUS),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("uses_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_public_invitations_id"), "public_invitations", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_public_invitations_token_hash"),
        "public_invitations",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_public_invitations_token_prefix"),
        "public_invitations",
        ["token_prefix"],
        unique=False,
    )
    op.create_index(
        op.f("ix_public_invitations_journey_type"),
        "public_invitations",
        ["journey_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_public_invitations_organization_id"),
        "public_invitations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_public_invitations_location_id"),
        "public_invitations",
        ["location_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_public_invitations_status"),
        "public_invitations",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_public_invitations_expires_at"),
        "public_invitations",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_public_invitations_expires_at"), table_name="public_invitations"
    )
    op.drop_index(
        op.f("ix_public_invitations_status"), table_name="public_invitations"
    )
    op.drop_index(
        op.f("ix_public_invitations_location_id"), table_name="public_invitations"
    )
    op.drop_index(
        op.f("ix_public_invitations_organization_id"),
        table_name="public_invitations",
    )
    op.drop_index(
        op.f("ix_public_invitations_journey_type"), table_name="public_invitations"
    )
    op.drop_index(
        op.f("ix_public_invitations_token_prefix"), table_name="public_invitations"
    )
    op.drop_index(
        op.f("ix_public_invitations_token_hash"), table_name="public_invitations"
    )
    op.drop_index(op.f("ix_public_invitations_id"), table_name="public_invitations")
    op.drop_table("public_invitations")
    bind = op.get_bind()
    PUBLIC_INVITATION_STATUS.drop(bind, checkfirst=True)
