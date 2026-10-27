"""Add global participant registration data

Revision ID: f1b3c5d7e9a2
Revises: e6a2b8c4d913
Create Date: 2026-10-27 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f1b3c5d7e9a2"
down_revision: Union[str, Sequence[str], None] = "e6a2b8c4d913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INVITATION_PURPOSE = postgresql.ENUM(
    "GLOBAL_REGISTRATION",
    "PROFESSIONAL_NETWORK",
    "LOCATION_REPRESENTATIVE",
    "MISSION_PARTICIPANT",
    name="invitationpurpose",
)
PARTICIPANT_VALIDATION_STATUS = postgresql.ENUM(
    "PENDING",
    "VALIDATED",
    "REJECTED",
    "SUSPENDED",
    "UPDATE_REQUIRED",
    name="participantvalidationstatus",
)
PARTICIPANT_VALIDATION_SCOPE = postgresql.ENUM(
    "GLOBAL",
    "PROFILE",
    "DOCUMENTS",
    "BANK",
    "FAMILY",
    "QUALIFICATIONS",
    name="participantvalidationscope",
)
PARTICIPANT_BANK_ACCOUNT_STATUS = postgresql.ENUM(
    "PENDING",
    "VERIFIED",
    "REJECTED",
    "DISABLED",
    name="participantbankaccountstatus",
)
PARTICIPANT_CLIENT_LINK_STATUS = postgresql.ENUM(
    "INVITED",
    "ACTIVE",
    "SUSPENDED",
    "ENDED",
    name="participantclientlinkstatus",
)
REGISTRATION_DRAFT_STATUS = postgresql.ENUM(
    "IN_PROGRESS",
    "SUBMITTED",
    "EXPIRED",
    name="registrationdraftstatus",
)

ENUMS = (
    INVITATION_PURPOSE,
    PARTICIPANT_VALIDATION_STATUS,
    PARTICIPANT_VALIDATION_SCOPE,
    PARTICIPANT_BANK_ACCOUNT_STATUS,
    PARTICIPANT_CLIENT_LINK_STATUS,
    REGISTRATION_DRAFT_STATUS,
)


def _column_enum(enum_type: postgresql.ENUM) -> postgresql.ENUM:
    return postgresql.ENUM(*enum_type.enums, name=enum_type.name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.add_column(
        "person_profiles",
        sa.Column(
            "cadastral_status",
            _column_enum(PARTICIPANT_VALIDATION_STATUS),
            server_default="PENDING",
            nullable=False,
        ),
    )
    op.add_column(
        "person_profiles",
        sa.Column("cadastral_status_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_person_profiles_cadastral_status"),
        "person_profiles",
        ["cadastral_status"],
        unique=False,
    )

    op.add_column(
        "missions",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_missions_organization_id",
        "missions",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_missions_organization_id"),
        "missions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_missions_required_function"),
        "missions",
        ["required_function"],
        unique=False,
    )
    bind.execute(
        sa.text(
            """
            UPDATE missions m
            SET organization_id = l.organization_id
            FROM locations l
            WHERE m.location_id = l.id
              AND m.organization_id IS NULL
            """
        )
    )

    for table in ("invitations", "public_invitations"):
        op.add_column(
            table,
            sa.Column(
                "purpose",
                _column_enum(INVITATION_PURPOSE),
                server_default="GLOBAL_REGISTRATION",
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("required_data_categories", sa.JSON(), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_mission_id",
            table,
            "missions",
            ["mission_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            op.f(f"ix_{table}_purpose"), table, ["purpose"], unique=False
        )
        op.create_index(
            op.f(f"ix_{table}_mission_id"), table, ["mission_id"], unique=False
        )

    op.add_column(
        "participant_consents",
        sa.Column("data_category", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "participant_consents",
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_participant_consents_data_category"),
        "participant_consents",
        ["data_category"],
        unique=False,
    )

    op.create_table(
        "participant_bank_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_code", sa.String(length=10), nullable=False),
        sa.Column("bank_name", sa.Text(), nullable=False),
        sa.Column("branch", sa.Text(), nullable=False),
        sa.Column("account_number", sa.Text(), nullable=False),
        sa.Column(
            "account_type", sa.String(length=20), server_default="CHECKING", nullable=False
        ),
        sa.Column("holder_name", sa.Text(), nullable=False),
        sa.Column("holder_cpf", sa.Text(), nullable=True),
        sa.Column("holder_cpf_hash", sa.String(length=64), nullable=True),
        sa.Column("pix_key_type", sa.String(length=20), nullable=True),
        sa.Column("pix_key", sa.Text(), nullable=True),
        sa.Column("account_fingerprint", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            _column_enum(PARTICIPANT_BANK_ACCOUNT_STATUS),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("verified_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["verified_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "account_fingerprint", name="uq_participant_bank_fingerprint"
        ),
    )
    for column in ("id", "user_id", "holder_cpf_hash", "status"):
        op.create_index(
            op.f(f"ix_participant_bank_accounts_{column}"),
            "participant_bank_accounts",
            [column],
            unique=False,
        )

    op.create_table(
        "participant_family_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("relationship", sa.String(length=40), nullable=False),
        sa.Column("birth_date", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("cpf", sa.Text(), nullable=True),
        sa.Column("cpf_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "is_legal_guardian", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("authorization_reference", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "user_id", "relationship", "cpf_hash"):
        op.create_index(
            op.f(f"ix_participant_family_members_{column}"),
            "participant_family_members",
            [column],
            unique=False,
        )

    op.create_table(
        "participant_client_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "purpose", sa.String(length=40), server_default="OPERATIONAL", nullable=False
        ),
        sa.Column(
            "status",
            _column_enum(PARTICIPANT_CLIENT_LINK_STATUS),
            server_default="INVITED",
            nullable=False,
        ),
        sa.Column("source_invitation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "source_public_invitation_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("source_mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "valid_from", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_invitation_id"], ["invitations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_public_invitation_id"],
            ["public_invitations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_mission_id"], ["missions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "organization_id", name="uq_participant_client_link"
        ),
    )
    for column in ("id", "user_id", "organization_id", "purpose", "status"):
        op.create_index(
            op.f(f"ix_participant_client_links_{column}"),
            "participant_client_links",
            [column],
            unique=False,
        )

    op.create_table(
        "participant_validation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "scope", _column_enum(PARTICIPANT_VALIDATION_SCOPE), nullable=False
        ),
        sa.Column(
            "status",
            _column_enum(PARTICIPANT_VALIDATION_STATUS),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "user_id", "scope", "status", "organization_id", "created_at"):
        op.create_index(
            op.f(f"ix_participant_validation_events_{column}"),
            "participant_validation_events",
            [column],
            unique=False,
        )

    op.create_table(
        "registration_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("invitation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "public_invitation_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("data_encrypted", sa.Text(), nullable=True),
        sa.Column("current_step", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "status",
            _column_enum(REGISTRATION_DRAFT_STATUS),
            server_default="IN_PROGRESS",
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["invitation_id"], ["invitations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["public_invitation_id"],
            ["public_invitations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "token_prefix", "user_id", "status", "expires_at"):
        op.create_index(
            op.f(f"ix_registration_drafts_{column}"),
            "registration_drafts",
            [column],
            unique=False,
        )
    op.create_index(
        op.f("ix_registration_drafts_token_hash"),
        "registration_drafts",
        ["token_hash"],
        unique=True,
    )

    op.alter_column("person_profiles", "cadastral_status", server_default=None)
    for table in ("invitations", "public_invitations"):
        op.alter_column(table, "purpose", server_default=None)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_registration_drafts_token_hash"), table_name="registration_drafts"
    )
    for column in ("expires_at", "status", "user_id", "token_prefix", "id"):
        op.drop_index(
            op.f(f"ix_registration_drafts_{column}"), table_name="registration_drafts"
        )
    op.drop_table("registration_drafts")

    for column in (
        "created_at",
        "organization_id",
        "status",
        "scope",
        "user_id",
        "id",
    ):
        op.drop_index(
            op.f(f"ix_participant_validation_events_{column}"),
            table_name="participant_validation_events",
        )
    op.drop_table("participant_validation_events")

    for column in ("status", "purpose", "organization_id", "user_id", "id"):
        op.drop_index(
            op.f(f"ix_participant_client_links_{column}"),
            table_name="participant_client_links",
        )
    op.drop_table("participant_client_links")

    for column in ("cpf_hash", "relationship", "user_id", "id"):
        op.drop_index(
            op.f(f"ix_participant_family_members_{column}"),
            table_name="participant_family_members",
        )
    op.drop_table("participant_family_members")

    for column in ("status", "holder_cpf_hash", "user_id", "id"):
        op.drop_index(
            op.f(f"ix_participant_bank_accounts_{column}"),
            table_name="participant_bank_accounts",
        )
    op.drop_table("participant_bank_accounts")

    op.drop_index(
        op.f("ix_participant_consents_data_category"),
        table_name="participant_consents",
    )
    op.drop_column("participant_consents", "retention_until")
    op.drop_column("participant_consents", "data_category")

    for table in ("public_invitations", "invitations"):
        op.drop_index(op.f(f"ix_{table}_mission_id"), table_name=table)
        op.drop_index(op.f(f"ix_{table}_purpose"), table_name=table)
        op.drop_constraint(f"fk_{table}_mission_id", table, type_="foreignkey")
        op.drop_column(table, "required_data_categories")
        op.drop_column(table, "mission_id")
        op.drop_column(table, "purpose")

    op.drop_index(op.f("ix_missions_required_function"), table_name="missions")
    op.drop_index(op.f("ix_missions_organization_id"), table_name="missions")
    op.drop_constraint("fk_missions_organization_id", "missions", type_="foreignkey")
    op.drop_column("missions", "organization_id")

    op.drop_index(
        op.f("ix_person_profiles_cadastral_status"), table_name="person_profiles"
    )
    op.drop_column("person_profiles", "cadastral_status_updated_at")
    op.drop_column("person_profiles", "cadastral_status")

    bind = op.get_bind()
    for enum_type in reversed(ENUMS):
        enum_type.drop(bind, checkfirst=True)
