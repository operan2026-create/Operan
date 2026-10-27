"""Global account, independent journeys, invitations and governance

Revision ID: c7a1e4d2b9f0
Revises: 9f1c2b3d4e5f
Create Date: 2026-10-26 00:00:00.000000

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c7a1e4d2b9f0"
down_revision: Union[str, Sequence[str], None] = "9f1c2b3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JOURNEY_TYPE = postgresql.ENUM("LOCATIONS", "PROFESSIONALS", name="journeytype")
JOURNEY_STATUS = postgresql.ENUM(
    "PENDING", "ACTIVE", "SUSPENDED", "INACTIVE", "REJECTED", name="journeystatus"
)
INVITATION_STATUS = postgresql.ENUM(
    "PENDING", "ACCEPTED", "REVOKED", "EXPIRED", name="invitationstatus"
)
REPRESENTATIVE_LINK_STATUS = postgresql.ENUM(
    "INVITED", "ACTIVE", "SUSPENDED", "ENDED", name="representativelinkstatus"
)
WORKFLOW_STAGE = postgresql.ENUM(
    "CAPTURE", "DOCUMENTATION", "INSPECTION", "RELEASE", name="workflowstage"
)
WORKFLOW_STATUS = postgresql.ENUM(
    "PENDING", "SUBMITTED", "APPROVED", "REJECTED", name="workflowstatus"
)
DOCUMENT_STATUS = postgresql.ENUM(
    "PENDING", "APPROVED", "REJECTED", name="documentstatus"
)
DOCUMENT_OWNER_TYPE = postgresql.ENUM(
    "PERSON", "LOCATION", "REPRESENTATIVE_LINK", name="documentownertype"
)
QUALIFICATION_STATUS = postgresql.ENUM(
    "PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED", name="qualificationstatus"
)
APPLICATION_STATUS = postgresql.ENUM(
    "APPLIED", "WITHDRAWN", "SELECTED", "REJECTED", name="applicationstatus"
)
COURSE_AUDIENCE = postgresql.ENUM(
    "GLOBAL", "LOCATIONS", "PROFESSIONALS", name="courseaudience"
)

ENUMS = [
    JOURNEY_TYPE,
    JOURNEY_STATUS,
    INVITATION_STATUS,
    REPRESENTATIVE_LINK_STATUS,
    WORKFLOW_STAGE,
    WORKFLOW_STATUS,
    DOCUMENT_STATUS,
    DOCUMENT_OWNER_TYPE,
    QUALIFICATION_STATUS,
    APPLICATION_STATUS,
    COURSE_AUDIENCE,
]


def _column_enum(enum_type: postgresql.ENUM) -> postgresql.ENUM:
    return postgresql.ENUM(*enum_type.enums, name=enum_type.name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("email_hash", sa.String(), nullable=False),
        sa.Column("email_encrypted", sa.String(), nullable=False),
        sa.Column("journey_type", _column_enum(JOURNEY_TYPE), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            _column_enum(INVITATION_STATUS),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invitations_id"), "invitations", ["id"], unique=False)
    op.create_index(
        op.f("ix_invitations_token_hash"), "invitations", ["token_hash"], unique=True
    )
    op.create_index(
        op.f("ix_invitations_token_prefix"), "invitations", ["token_prefix"], unique=False
    )
    op.create_index(
        op.f("ix_invitations_email_hash"), "invitations", ["email_hash"], unique=False
    )
    op.create_index(
        op.f("ix_invitations_journey_type"), "invitations", ["journey_type"], unique=False
    )
    op.create_index(
        op.f("ix_invitations_organization_id"),
        "invitations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_invitations_location_id"), "invitations", ["location_id"], unique=False
    )
    op.create_index(op.f("ix_invitations_status"), "invitations", ["status"], unique=False)
    op.create_index(
        op.f("ix_invitations_expires_at"), "invitations", ["expires_at"], unique=False
    )

    op.create_table(
        "person_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("social_name", sa.String(), nullable=True),
        sa.Column("cpf_hash", sa.String(), nullable=False),
        sa.Column("cpf_encrypted", sa.String(), nullable=False),
        sa.Column("phone_encrypted", sa.String(), nullable=False),
        sa.Column("rg_encrypted", sa.String(), nullable=True),
        sa.Column("rg_hash", sa.String(), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=30), nullable=True),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("zip_code", sa.String(length=10), nullable=True),
        sa.Column("address_street", sa.String(), nullable=True),
        sa.Column("address_number", sa.String(length=20), nullable=True),
        sa.Column("address_complement", sa.String(), nullable=True),
        sa.Column("address_neighborhood", sa.String(), nullable=True),
        sa.Column("emergency_contact_name", sa.String(), nullable=True),
        sa.Column("emergency_contact_phone_encrypted", sa.String(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("profile_completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_person_profiles_id"), "person_profiles", ["id"], unique=False)
    op.create_index(
        op.f("ix_person_profiles_user_id"), "person_profiles", ["user_id"], unique=True
    )
    op.create_index(
        op.f("ix_person_profiles_cpf_hash"), "person_profiles", ["cpf_hash"], unique=True
    )
    op.create_index(
        op.f("ix_person_profiles_rg_hash"), "person_profiles", ["rg_hash"], unique=False
    )
    op.create_index(
        op.f("ix_person_profiles_city"), "person_profiles", ["city"], unique=False
    )
    op.create_index(
        op.f("ix_person_profiles_state"), "person_profiles", ["state"], unique=False
    )

    op.create_table(
        "journey_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journey_type", _column_enum(JOURNEY_TYPE), nullable=False),
        sa.Column(
            "status", _column_enum(JOURNEY_STATUS), server_default="PENDING", nullable=False
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requirements_met_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_invitation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_invitation_id"], ["invitations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "journey_type", name="uq_user_journey_type"),
    )
    op.create_index(
        op.f("ix_journey_enrollments_id"), "journey_enrollments", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_journey_enrollments_user_id"),
        "journey_enrollments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_journey_enrollments_journey_type"),
        "journey_enrollments",
        ["journey_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_journey_enrollments_status"),
        "journey_enrollments",
        ["status"],
        unique=False,
    )

    op.create_table(
        "representative_school_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("representative_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            _column_enum(REPRESENTATIVE_LINK_STATUS),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column("responsibilities", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invitation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["representative_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invitation_id"], ["invitations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "representative_user_id", "location_id", name="uq_representative_school"
        ),
    )
    op.create_index(
        op.f("ix_representative_school_links_id"),
        "representative_school_links",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_representative_school_links_representative_user_id"),
        "representative_school_links",
        ["representative_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_representative_school_links_location_id"),
        "representative_school_links",
        ["location_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_representative_school_links_status"),
        "representative_school_links",
        ["status"],
        unique=False,
    )

    op.create_table(
        "location_workflow_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", _column_enum(WORKFLOW_STAGE), nullable=False),
        sa.Column(
            "status", _column_enum(WORKFLOW_STATUS), server_default="PENDING", nullable=False
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_location_workflow_events_id"),
        "location_workflow_events",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_location_workflow_events_location_id"),
        "location_workflow_events",
        ["location_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_location_workflow_events_stage"),
        "location_workflow_events",
        ["stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_location_workflow_events_status"),
        "location_workflow_events",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_location_workflow_events_created_at"),
        "location_workflow_events",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_type", _column_enum(DOCUMENT_OWNER_TYPE), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "status", _column_enum(DOCUMENT_STATUS), server_default="PENDING", nullable=False
        ),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(op.f("ix_documents_id"), "documents", ["id"], unique=False)
    op.create_index(
        op.f("ix_documents_owner_type"), "documents", ["owner_type"], unique=False
    )
    op.create_index(op.f("ix_documents_owner_id"), "documents", ["owner_id"], unique=False)
    op.create_index(
        op.f("ix_documents_document_type"), "documents", ["document_type"], unique=False
    )
    op.create_index(op.f("ix_documents_sha256"), "documents", ["sha256"], unique=False)
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)

    op.create_table(
        "qualification_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("function_name", sa.String(length=40), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("validity_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["course_version_id"], ["course_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_version_id",
            "function_name",
            name="uq_qualification_requirement",
        ),
    )
    op.create_index(
        op.f("ix_qualification_requirements_id"),
        "qualification_requirements",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_qualification_requirements_course_version_id"),
        "qualification_requirements",
        ["course_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_qualification_requirements_function_name"),
        "qualification_requirements",
        ["function_name"],
        unique=False,
    )

    op.create_table(
        "professional_qualifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("function_name", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            _column_enum(QUALIFICATION_STATUS),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column("certification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("course_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("suspended_reason", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["certification_id"], ["certifications.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["course_version_id"], ["course_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "function_name", name="uq_user_professional_function"
        ),
    )
    op.create_index(
        op.f("ix_professional_qualifications_id"),
        "professional_qualifications",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_professional_qualifications_user_id"),
        "professional_qualifications",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_professional_qualifications_function_name"),
        "professional_qualifications",
        ["function_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_professional_qualifications_status"),
        "professional_qualifications",
        ["status"],
        unique=False,
    )

    op.create_table(
        "mission_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            _column_enum(APPLICATION_STATUS),
            server_default="APPLIED",
            nullable=False,
        ),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mission_id", "user_id", name="uq_mission_application"),
    )
    op.create_index(
        op.f("ix_mission_applications_id"), "mission_applications", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_mission_applications_mission_id"),
        "mission_applications",
        ["mission_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mission_applications_user_id"),
        "mission_applications",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mission_applications_status"), "mission_applications", ["status"], unique=False
    )

    op.create_table(
        "participant_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_type", sa.String(length=40), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("legal_basis", sa.String(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_participant_consents_id"), "participant_consents", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_participant_consents_user_id"),
        "participant_consents",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_participant_consents_consent_type"),
        "participant_consents",
        ["consent_type"],
        unique=False,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_public_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"], unique=False)
    op.create_index(
        op.f("ix_audit_logs_actor_user_id"), "audit_logs", ["actor_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_actor_public_id"),
        "audit_logs",
        ["actor_public_id"],
        unique=False,
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(
        op.f("ix_audit_logs_entity_type"), "audit_logs", ["entity_type"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_entity_id"), "audit_logs", ["entity_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False
    )

    op.add_column(
        "courses",
        sa.Column(
            "audience",
            _column_enum(COURSE_AUDIENCE),
            server_default=sa.text("'GLOBAL'"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_courses_audience"), "courses", ["audience"], unique=False
    )
    op.add_column("missions", sa.Column("required_function", sa.String(length=40), nullable=True))

    _backfill_global_profiles()
    _backfill_professional_journeys()


def _backfill_global_profiles() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT p.user_id, p.full_name, p.cpf_hash, p.cpf_encrypted,
                   p.phone_encrypted, p.city, p.state
            FROM professionals p
            LEFT JOIN person_profiles pp ON pp.user_id = p.user_id
            WHERE pp.id IS NULL
            """
        )
    ).mappings().all()
    if not rows:
        return
    table = sa.table(
        "person_profiles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("full_name", sa.String()),
        sa.column("cpf_hash", sa.String()),
        sa.column("cpf_encrypted", sa.String()),
        sa.column("phone_encrypted", sa.String()),
        sa.column("city", sa.String()),
        sa.column("state", sa.String()),
        sa.column("profile_completed", sa.Boolean()),
    )
    bind.execute(
        table.insert(),
        [
            {
                "id": uuid.uuid4(),
                "user_id": row["user_id"],
                "full_name": row["full_name"],
                "cpf_hash": row["cpf_hash"],
                "cpf_encrypted": row["cpf_encrypted"],
                "phone_encrypted": row["phone_encrypted"],
                "city": row["city"],
                "state": row["state"],
                "profile_completed": False,
            }
            for row in rows
        ],
    )


def _backfill_professional_journeys() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT p.user_id
            FROM professionals p
            LEFT JOIN journey_enrollments j
              ON j.user_id = p.user_id AND j.journey_type = 'PROFESSIONALS'
            WHERE j.id IS NULL
            """
        )
    ).mappings().all()
    if not rows:
        return
    table = sa.table(
        "journey_enrollments",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("journey_type", _column_enum(JOURNEY_TYPE)),
        sa.column("status", _column_enum(JOURNEY_STATUS)),
        sa.column("activated_at", sa.DateTime(timezone=True)),
    )
    bind.execute(
        table.insert(),
        [
            {
                "id": uuid.uuid4(),
                "user_id": row["user_id"],
                "journey_type": "PROFESSIONALS",
                "status": "ACTIVE",
                "activated_at": datetime.now(timezone.utc),
            }
            for row in rows
        ],
    )


def downgrade() -> None:
    op.drop_column("missions", "required_function")
    op.drop_index(op.f("ix_courses_audience"), table_name="courses")
    op.drop_column("courses", "audience")
    op.drop_table("audit_logs")
    op.drop_table("participant_consents")
    op.drop_table("mission_applications")
    op.drop_table("professional_qualifications")
    op.drop_table("qualification_requirements")
    op.drop_table("documents")
    op.drop_table("location_workflow_events")
    op.drop_table("representative_school_links")
    op.drop_table("journey_enrollments")
    op.drop_table("person_profiles")
    op.drop_table("invitations")

    bind = op.get_bind()
    for enum_type in reversed(ENUMS):
        enum_type.drop(bind, checkfirst=True)
