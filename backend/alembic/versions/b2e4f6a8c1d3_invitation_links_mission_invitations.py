"""Persist invitation links and add direct mission invitations

Revision ID: b2e4f6a8c1d3
Revises: c7a1e4d2b9f0
Create Date: 2026-10-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b2e4f6a8c1d3"
down_revision: Union[str, Sequence[str], None] = "c7a1e4d2b9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MISSION_INVITATION_STATUS = postgresql.ENUM(
    "INVITED", "ACCEPTED", "DECLINED", "CANCELLED", name="missioninvitationstatus"
)


def _column_enum(enum_type: postgresql.ENUM) -> postgresql.ENUM:
    return postgresql.ENUM(*enum_type.enums, name=enum_type.name, create_type=False)


def upgrade() -> None:
    op.add_column(
        "invitations", sa.Column("token_encrypted", sa.String(), nullable=True)
    )

    bind = op.get_bind()
    MISSION_INVITATION_STATUS.create(bind, checkfirst=True)
    op.create_table(
        "mission_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            _column_enum(MISSION_INVITATION_STATUS),
            server_default="INVITED",
            nullable=False,
        ),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mission_id", "user_id", name="uq_mission_invitation"),
    )
    op.create_index(
        op.f("ix_mission_invitations_id"), "mission_invitations", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_mission_invitations_mission_id"),
        "mission_invitations",
        ["mission_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mission_invitations_user_id"),
        "mission_invitations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mission_invitations_status"),
        "mission_invitations",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_mission_invitations_status"), table_name="mission_invitations"
    )
    op.drop_index(
        op.f("ix_mission_invitations_user_id"), table_name="mission_invitations"
    )
    op.drop_index(
        op.f("ix_mission_invitations_mission_id"), table_name="mission_invitations"
    )
    op.drop_index(op.f("ix_mission_invitations_id"), table_name="mission_invitations")
    op.drop_table("mission_invitations")
    bind = op.get_bind()
    MISSION_INVITATION_STATUS.drop(bind, checkfirst=True)
    op.drop_column("invitations", "token_encrypted")
