import enum
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.security.encrypted_types import EncryptedDate, EncryptedString, EncryptedText


class JourneyType(str, enum.Enum):
    LOCATIONS = "LOCATIONS"
    PROFESSIONALS = "PROFESSIONALS"


class JourneyStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"
    REJECTED = "REJECTED"


class InvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class PublicInvitationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class InvitationPurpose(str, enum.Enum):
    GLOBAL_REGISTRATION = "GLOBAL_REGISTRATION"
    PROFESSIONAL_NETWORK = "PROFESSIONAL_NETWORK"
    LOCATION_REPRESENTATIVE = "LOCATION_REPRESENTATIVE"
    MISSION_PARTICIPANT = "MISSION_PARTICIPANT"


class ParticipantDataCategory(str, enum.Enum):
    PROFILE = "PROFILE"
    CONTACT = "CONTACT"
    ADDRESS = "ADDRESS"
    BANK = "BANK"
    FAMILY = "FAMILY"
    DOCUMENTS = "DOCUMENTS"
    QUALIFICATIONS = "QUALIFICATIONS"


class ParticipantValidationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"
    UPDATE_REQUIRED = "UPDATE_REQUIRED"


class ParticipantValidationScope(str, enum.Enum):
    GLOBAL = "GLOBAL"
    PROFILE = "PROFILE"
    DOCUMENTS = "DOCUMENTS"
    BANK = "BANK"
    FAMILY = "FAMILY"
    QUALIFICATIONS = "QUALIFICATIONS"


class ParticipantBankAccountStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    DISABLED = "DISABLED"


class ParticipantClientLinkStatus(str, enum.Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ENDED = "ENDED"


class RegistrationDraftStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    EXPIRED = "EXPIRED"


class RepresentativeLinkStatus(str, enum.Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ENDED = "ENDED"


class WorkflowStage(str, enum.Enum):
    CAPTURE = "CAPTURE"
    DOCUMENTATION = "DOCUMENTATION"
    INSPECTION = "INSPECTION"
    RELEASE = "RELEASE"


class WorkflowStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DocumentStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DocumentOwnerType(str, enum.Enum):
    PERSON = "PERSON"
    LOCATION = "LOCATION"
    REPRESENTATIVE_LINK = "REPRESENTATIVE_LINK"


class QualificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class ApplicationStatus(str, enum.Enum):
    APPLIED = "APPLIED"
    WITHDRAWN = "WITHDRAWN"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


class MissionInvitationStatus(str, enum.Enum):
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"


class PersonProfile(Base):
    """Global personal data shared by every journey of the same account."""

    __tablename__ = "person_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    full_name = Column(EncryptedString, nullable=False)
    social_name = Column(EncryptedString, nullable=True)
    cpf_hash = Column(String, unique=True, nullable=False, index=True)
    cpf_encrypted = Column(String, nullable=False)
    phone_encrypted = Column(String, nullable=False)
    rg_encrypted = Column(String, nullable=True)
    rg_hash = Column(String, nullable=True, index=True)
    birth_date = Column(EncryptedDate, nullable=True)
    gender = Column(EncryptedString, nullable=True)

    city = Column(EncryptedString, nullable=False)
    state = Column(EncryptedString, nullable=False)
    zip_code = Column(EncryptedString, nullable=True)
    address_street = Column(EncryptedString, nullable=True)
    address_number = Column(EncryptedString, nullable=True)
    address_complement = Column(EncryptedString, nullable=True)
    address_neighborhood = Column(EncryptedString, nullable=True)

    emergency_contact_name = Column(EncryptedString, nullable=True)
    emergency_contact_phone_encrypted = Column(String, nullable=True)
    bio = Column(EncryptedText, nullable=True)
    avatar_data = Column(EncryptedText, nullable=True)
    avatar_mime_type = Column(String(40), nullable=True)
    avatar_sha256 = Column(String(64), nullable=True)
    avatar_updated_at = Column(DateTime(timezone=True), nullable=True)
    profile_completed = Column(Boolean, default=False, nullable=False)
    cadastral_status = Column(
        Enum(ParticipantValidationStatus),
        default=ParticipantValidationStatus.PENDING,
        nullable=False,
        index=True,
    )
    cadastral_status_updated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")


class ParticipantBankAccount(Base):
    __tablename__ = "participant_bank_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bank_code = Column(String(10), nullable=False)
    bank_name = Column(EncryptedString, nullable=False)
    branch = Column(EncryptedString, nullable=False)
    account_number = Column(EncryptedString, nullable=False)
    account_type = Column(String(20), default="CHECKING", nullable=False)
    holder_name = Column(EncryptedString, nullable=False)
    holder_cpf = Column(EncryptedString, nullable=True)
    holder_cpf_hash = Column(String(64), nullable=True, index=True)
    pix_key_type = Column(String(20), nullable=True)
    pix_key = Column(EncryptedString, nullable=True)
    account_fingerprint = Column(String(64), nullable=True)
    status = Column(
        Enum(ParticipantBankAccountStatus),
        default=ParticipantBankAccountStatus.PENDING,
        nullable=False,
        index=True,
    )
    is_primary = Column(Boolean, default=False, nullable=False)
    verified_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "user_id", "account_fingerprint", name="uq_participant_bank_fingerprint"
        ),
    )


class ParticipantFamilyMember(Base):
    __tablename__ = "participant_family_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name = Column(EncryptedString, nullable=False)
    kinship = Column("relationship", String(40), nullable=False, index=True)
    birth_date = Column(EncryptedDate, nullable=True)
    phone = Column(EncryptedString, nullable=True)
    cpf = Column(EncryptedString, nullable=True)
    cpf_hash = Column(String(64), nullable=True, index=True)
    is_legal_guardian = Column(Boolean, default=False, nullable=False)
    authorization_reference = Column(EncryptedString, nullable=True)
    notes = Column(EncryptedText, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")


class ParticipantClientLink(Base):
    __tablename__ = "participant_client_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose = Column(String(40), default="OPERATIONAL", nullable=False, index=True)
    status = Column(
        Enum(ParticipantClientLinkStatus),
        default=ParticipantClientLinkStatus.INVITED,
        nullable=False,
        index=True,
    )
    source_invitation_id = Column(
        UUID(as_uuid=True), ForeignKey("invitations.id", ondelete="SET NULL"), nullable=True
    )
    source_public_invitation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public_invitations.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_mission_id = Column(
        UUID(as_uuid=True), ForeignKey("missions.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    valid_from = Column(DateTime(timezone=True), server_default=func.now())
    valid_until = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "user_id", "organization_id", name="uq_participant_client_link"
        ),
    )

    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization")
    mission = relationship("Mission")
    created_by = relationship("User", foreign_keys=[created_by_user_id])


class ParticipantValidationEvent(Base):
    __tablename__ = "participant_validation_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope = Column(Enum(ParticipantValidationScope), nullable=False, index=True)
    status = Column(
        Enum(ParticipantValidationStatus),
        default=ParticipantValidationStatus.PENDING,
        nullable=False,
        index=True,
    )
    reviewer_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes = Column(EncryptedText, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_user_id])
    organization = relationship("Organization")


class RegistrationDraft(Base):
    __tablename__ = "registration_drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    token_prefix = Column(String(16), nullable=False, index=True)
    invitation_id = Column(
        UUID(as_uuid=True), ForeignKey("invitations.id", ondelete="SET NULL"), nullable=True
    )
    public_invitation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public_invitations.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    data_encrypted = Column(EncryptedText, nullable=True)
    current_step = Column(Integer, default=1, nullable=False)
    status = Column(
        Enum(RegistrationDraftStatus),
        default=RegistrationDraftStatus.IN_PROGRESS,
        nullable=False,
        index=True,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    invitation = relationship("Invitation")
    public_invitation = relationship("PublicInvitation")
    user = relationship("User")


class JourneyEnrollment(Base):
    __tablename__ = "journey_enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    journey_type = Column(Enum(JourneyType), nullable=False, index=True)
    status = Column(Enum(JourneyStatus), default=JourneyStatus.PENDING, nullable=False, index=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    requirements_met_at = Column(DateTime(timezone=True), nullable=True)
    source_invitation_id = Column(
        UUID(as_uuid=True), ForeignKey("invitations.id", ondelete="SET NULL"), nullable=True
    )
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "journey_type", name="uq_user_journey_type"),
    )

    user = relationship("User")


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    token_prefix = Column(String(16), nullable=False, index=True)
    token_encrypted = Column(String, nullable=True)
    email_hash = Column(String, nullable=False, index=True)
    email_encrypted = Column(String, nullable=False)

    journey_type = Column(Enum(JourneyType), nullable=False, index=True)
    purpose = Column(
        Enum(InvitationPurpose),
        default=InvitationPurpose.GLOBAL_REGISTRATION,
        nullable=False,
        index=True,
    )
    mission_id = Column(
        UUID(as_uuid=True), ForeignKey("missions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    required_data_categories = Column(JSON, default=list, nullable=True)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location_id = Column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status = Column(
        Enum(InvitationStatus), default=InvitationStatus.PENDING, nullable=False, index=True
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    location = relationship("Location")


class PublicInvitation(Base):
    __tablename__ = "public_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    token_prefix = Column(String(16), nullable=False, index=True)
    token_encrypted = Column(String, nullable=True)
    label = Column(String, nullable=True)

    journey_type = Column(Enum(JourneyType), nullable=False, index=True)
    purpose = Column(
        Enum(InvitationPurpose),
        default=InvitationPurpose.GLOBAL_REGISTRATION,
        nullable=False,
        index=True,
    )
    mission_id = Column(
        UUID(as_uuid=True), ForeignKey("missions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    required_data_categories = Column(JSON, default=list, nullable=True)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location_id = Column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status = Column(
        Enum(PublicInvitationStatus),
        default=PublicInvitationStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    max_uses = Column(Integer, nullable=True)
    uses_count = Column(Integer, default=0, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    location = relationship("Location")


class RepresentativeSchoolLink(Base):
    __tablename__ = "representative_school_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    representative_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id = Column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(
        Enum(RepresentativeLinkStatus),
        default=RepresentativeLinkStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    responsibilities = Column(JSON, nullable=True)
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    invitation_id = Column(
        UUID(as_uuid=True), ForeignKey("invitations.id", ondelete="SET NULL"), nullable=True
    )
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("representative_user_id", "location_id", name="uq_representative_school"),
    )

    location = relationship("Location")


class LocationWorkflowEvent(Base):
    __tablename__ = "location_workflow_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    location_id = Column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage = Column(Enum(WorkflowStage), nullable=False, index=True)
    status = Column(Enum(WorkflowStatus), default=WorkflowStatus.PENDING, nullable=False, index=True)
    actor_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    owner_type = Column(Enum(DocumentOwnerType), nullable=False, index=True)
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    document_type = Column(String(40), nullable=False, index=True)
    file_name = Column(EncryptedString, nullable=False)
    storage_key = Column(String, unique=True, nullable=False)
    mime_type = Column(String(120), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)

    status = Column(
        Enum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False, index=True
    )
    uploaded_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class QualificationRequirement(Base):
    __tablename__ = "qualification_requirements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    course_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    function_name = Column(String(40), nullable=False, index=True)
    is_required = Column(Boolean, default=True, nullable=False)
    validity_days = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    course_version = relationship("CourseVersion")

    __table_args__ = (
        UniqueConstraint(
            "course_version_id", "function_name", name="uq_qualification_requirement"
        ),
    )


class ProfessionalQualification(Base):
    __tablename__ = "professional_qualifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    function_name = Column(String(40), nullable=False, index=True)
    status = Column(
        Enum(QualificationStatus), default=QualificationStatus.ACTIVE, nullable=False, index=True
    )
    certification_id = Column(
        UUID(as_uuid=True), ForeignKey("certifications.id", ondelete="SET NULL"), nullable=True
    )
    course_version_id = Column(
        UUID(as_uuid=True), ForeignKey("course_versions.id", ondelete="SET NULL"), nullable=True
    )
    issued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    issued_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    suspended_reason = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "function_name", name="uq_user_professional_function"),
    )


class MissionApplication(Base):
    __tablename__ = "mission_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    mission_id = Column(
        UUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(
        Enum(ApplicationStatus), default=ApplicationStatus.APPLIED, nullable=False, index=True
    )
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("mission_id", "user_id", name="uq_mission_application"),
    )


class MissionInvitation(Base):
    __tablename__ = "mission_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    mission_id = Column(
        UUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status = Column(
        Enum(MissionInvitationStatus),
        default=MissionInvitationStatus.INVITED,
        nullable=False,
        index=True,
    )
    message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("mission_id", "user_id", name="uq_mission_invitation"),
    )


class ParticipantConsent(Base):
    __tablename__ = "participant_consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    consent_type = Column(String(40), nullable=False, index=True)
    data_category = Column(String(40), nullable=True, index=True)
    policy_version = Column(String(40), nullable=False)
    purpose = Column(String, nullable=False)
    legal_basis = Column(String, nullable=False)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    retention_until = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    actor_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_public_id = Column(String, nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(60), nullable=False, index=True)
    entity_id = Column(String, nullable=True, index=True)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    details = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    actor = relationship("User")
