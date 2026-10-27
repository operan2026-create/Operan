import enum
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, UUID4, field_validator

from app.models.academy import CourseAudience
from app.models.participant import (
    ApplicationStatus,
    DocumentOwnerType,
    DocumentStatus,
    InvitationPurpose,
    InvitationStatus,
    JourneyStatus,
    ParticipantDataCategory,
    JourneyType,
    MissionInvitationStatus,
    ParticipantBankAccountStatus,
    ParticipantValidationScope,
    ParticipantValidationStatus,
    PublicInvitationStatus,
    QualificationStatus,
    RegistrationDraftStatus,
    RepresentativeLinkStatus,
    WorkflowStage,
    WorkflowStatus,
)


class ProfessionalFunction(str, enum.Enum):
    FISCAL_SALA = "FISCAL_SALA"
    VOLANTE = "VOLANTE"
    CHEFE_SALA = "CHEFE_SALA"
    APOIO = "APOIO"
    SUPERVISOR = "SUPERVISOR"
    FISCAL_BANHEIRO = "FISCAL_BANHEIRO"
    COORDENADOR = "COORDENADOR"


def normalize_cpf(value: str) -> str:
    digits = "".join(filter(str.isdigit, value or ""))
    if len(digits) != 11:
        raise ValueError("CPF deve conter 11 digitos.")
    return digits


def only_digits(value: Optional[str]) -> str:
    return "".join(filter(str.isdigit, value or ""))


def mask_cpf(value: Optional[str]) -> str:
    digits = only_digits(value)
    if len(digits) != 11:
        return "***.***.***-**"
    return f"***.***.***-{digits[-2:]}"


def mask_phone(value: Optional[str]) -> str:
    digits = only_digits(value)
    if len(digits) < 4:
        return "(**) *****-****"
    return f"(**) *****-{digits[-4:]}"


def mask_generic(value: Optional[str], visible: int = 2) -> Optional[str]:
    if not value:
        return None
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * max(3, len(value) - visible) + value[-visible:]


def mask_account_number(value: Optional[str]) -> str:
    digits = only_digits(value)
    if not digits:
        return "****"
    return f"****{digits[-4:]}"


BANK_ACCOUNT_TYPES = {"CHECKING", "SAVINGS", "PAYMENT"}
PIX_KEY_TYPES = {"CPF", "CNPJ", "EMAIL", "PHONE", "RANDOM"}


class BankAccountCreate(BaseModel):
    bank_code: str = Field(min_length=1, max_length=10)
    bank_name: str = Field(min_length=2, max_length=120)
    branch: str = Field(min_length=1, max_length=20)
    account_number: str = Field(min_length=1, max_length=30)
    account_type: str = Field(default="CHECKING", max_length=20)
    holder_name: str = Field(min_length=3, max_length=200)
    holder_cpf: Optional[str] = None
    pix_key_type: Optional[str] = Field(default=None, max_length=20)
    pix_key: Optional[str] = Field(default=None, max_length=200)
    is_primary: bool = False

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, value: str) -> str:
        normalized = value.upper().strip()
        if normalized not in BANK_ACCOUNT_TYPES:
            raise ValueError("Tipo de conta bancaria invalido.")
        return normalized

    @field_validator("pix_key_type")
    @classmethod
    def validate_pix_key_type(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        normalized = value.upper().strip()
        if normalized not in PIX_KEY_TYPES:
            raise ValueError("Tipo de chave Pix invalido.")
        return normalized

    @field_validator("holder_cpf")
    @classmethod
    def validate_holder_cpf(cls, value: Optional[str]) -> Optional[str]:
        return normalize_cpf(value) if value else None


class BankAccountUpdate(BaseModel):
    bank_code: Optional[str] = Field(default=None, min_length=1, max_length=10)
    bank_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    branch: Optional[str] = Field(default=None, min_length=1, max_length=20)
    account_number: Optional[str] = Field(default=None, min_length=1, max_length=30)
    account_type: Optional[str] = Field(default=None, max_length=20)
    holder_name: Optional[str] = Field(default=None, min_length=3, max_length=200)
    holder_cpf: Optional[str] = None
    pix_key_type: Optional[str] = Field(default=None, max_length=20)
    pix_key: Optional[str] = Field(default=None, max_length=200)
    is_primary: Optional[bool] = None

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.upper().strip()
        if normalized not in BANK_ACCOUNT_TYPES:
            raise ValueError("Tipo de conta bancaria invalido.")
        return normalized

    @field_validator("pix_key_type")
    @classmethod
    def validate_pix_key_type(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        normalized = value.upper().strip()
        if normalized not in PIX_KEY_TYPES:
            raise ValueError("Tipo de chave Pix invalido.")
        return normalized

    @field_validator("holder_cpf")
    @classmethod
    def validate_holder_cpf(cls, value: Optional[str]) -> Optional[str]:
        return normalize_cpf(value) if value else None


class BankAccountResponse(BaseModel):
    id: UUID4
    bank_code: str
    bank_name: str
    branch: str
    account_number_masked: str
    account_type: str
    holder_name: str
    holder_cpf_masked: Optional[str] = None
    pix_key_type: Optional[str] = None
    pix_key_masked: Optional[str] = None
    status: ParticipantBankAccountStatus
    is_primary: bool
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class FamilyMemberCreate(BaseModel):
    full_name: str = Field(min_length=3, max_length=200)
    kinship: str = Field(min_length=2, max_length=40)
    birth_date: Optional[date] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    cpf: Optional[str] = None
    is_legal_guardian: bool = False
    authorization_reference: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: Optional[str]) -> Optional[str]:
        return normalize_cpf(value) if value else None

    @field_validator("kinship")
    @classmethod
    def normalize_kinship(cls, value: str) -> str:
        return value.strip().upper()


class FamilyMemberUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=3, max_length=200)
    kinship: Optional[str] = Field(default=None, min_length=2, max_length=40)
    birth_date: Optional[date] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    cpf: Optional[str] = None
    is_legal_guardian: Optional[bool] = None
    authorization_reference: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: Optional[str]) -> Optional[str]:
        return normalize_cpf(value) if value else None

    @field_validator("kinship")
    @classmethod
    def normalize_kinship(cls, value: Optional[str]) -> Optional[str]:
        return value.strip().upper() if value else None


class FamilyMemberResponse(BaseModel):
    id: UUID4
    full_name: str
    kinship: str
    birth_date: Optional[date] = None
    phone_masked: Optional[str] = None
    cpf_masked: Optional[str] = None
    is_legal_guardian: bool
    authorization_reference: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PersonProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=3, max_length=200)
    social_name: Optional[str] = Field(default=None, max_length=200)
    birth_date: Optional[date] = None
    gender: Optional[str] = Field(default=None, max_length=30)
    phone: Optional[str] = Field(default=None, max_length=30)
    rg: Optional[str] = Field(default=None, max_length=30)
    city: Optional[str] = Field(default=None, min_length=2, max_length=120)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    zip_code: Optional[str] = Field(default=None, max_length=10)
    address_street: Optional[str] = Field(default=None, max_length=200)
    address_number: Optional[str] = Field(default=None, max_length=20)
    address_complement: Optional[str] = Field(default=None, max_length=120)
    address_neighborhood: Optional[str] = Field(default=None, max_length=120)
    emergency_contact_name: Optional[str] = Field(default=None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=30)
    bio: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else None


class AvatarUpdate(BaseModel):
    avatar_base64: str = Field(max_length=8_000_000)
    avatar_mime_type: str = Field(max_length=40)


class PersonProfileResponse(BaseModel):
    user_id: UUID4
    public_id: str
    email: EmailStr
    full_name: str
    social_name: Optional[str] = None
    cpf_masked: str
    phone_masked: str
    rg_masked: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    city: str
    state: str
    zip_code: Optional[str] = None
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    address_neighborhood: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone_masked: Optional[str] = None
    bio: Optional[str] = None
    has_avatar: bool = False
    avatar_url: Optional[str] = None
    profile_completed: bool
    cadastral_status: ParticipantValidationStatus = ParticipantValidationStatus.PENDING
    cadastral_status_updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class JourneyResponse(BaseModel):
    id: UUID4
    journey_type: JourneyType
    status: JourneyStatus
    activated_at: Optional[datetime] = None
    requirements_met_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AccountResponse(BaseModel):
    profile: PersonProfileResponse
    journeys: List[JourneyResponse] = []
    qualifications: List["QualificationResponse"] = []


class JourneyStatusUpdate(BaseModel):
    status: JourneyStatus
    notes: Optional[str] = Field(default=None, max_length=500)


class InvitationCreate(BaseModel):
    email: EmailStr
    journey_type: JourneyType
    purpose: InvitationPurpose = InvitationPurpose.GLOBAL_REGISTRATION
    mission_id: Optional[UUID4] = None
    required_data_categories: List[ParticipantDataCategory] = []
    organization_id: Optional[UUID4] = None
    location_id: Optional[UUID4] = None
    expires_in_days: int = Field(default=7, ge=1, le=30)


class InvitationCreatedResponse(BaseModel):
    id: UUID4
    email: EmailStr
    journey_type: JourneyType
    purpose: InvitationPurpose = InvitationPurpose.GLOBAL_REGISTRATION
    mission_id: Optional[UUID4] = None
    required_data_categories: List[ParticipantDataCategory] = []
    organization_id: Optional[UUID4] = None
    organization_name: Optional[str] = None
    location_id: Optional[UUID4] = None
    location_name: Optional[str] = None
    status: InvitationStatus
    expires_at: datetime
    token: str
    accept_path: str


class InvitationValidationResponse(BaseModel):
    valid: bool
    status: InvitationStatus
    email: EmailStr
    journey_type: JourneyType
    purpose: InvitationPurpose = InvitationPurpose.GLOBAL_REGISTRATION
    mission_id: Optional[UUID4] = None
    required_data_categories: List[ParticipantDataCategory] = []
    organization_id: Optional[UUID4] = None
    organization_name: Optional[str] = None
    location_id: Optional[UUID4] = None
    location_name: Optional[str] = None
    expires_at: datetime
    requires_account: bool


class PublicInvitationCreate(BaseModel):
    journey_type: JourneyType
    purpose: InvitationPurpose = InvitationPurpose.GLOBAL_REGISTRATION
    mission_id: Optional[UUID4] = None
    required_data_categories: List[ParticipantDataCategory] = []
    organization_id: Optional[UUID4] = None
    location_id: Optional[UUID4] = None
    label: Optional[str] = Field(default=None, max_length=120)
    expires_in_days: int = Field(default=30, ge=1, le=365)
    max_uses: Optional[int] = Field(default=None, ge=1, le=10000)


class PublicInvitationCreatedResponse(BaseModel):
    id: UUID4
    label: Optional[str] = None
    journey_type: JourneyType
    purpose: InvitationPurpose = InvitationPurpose.GLOBAL_REGISTRATION
    mission_id: Optional[UUID4] = None
    required_data_categories: List[ParticipantDataCategory] = []
    organization_id: Optional[UUID4] = None
    organization_name: Optional[str] = None
    location_id: Optional[UUID4] = None
    location_name: Optional[str] = None
    status: PublicInvitationStatus
    expires_at: datetime
    max_uses: Optional[int] = None
    uses_count: int
    token: str
    accept_path: str


class PublicInvitationResponse(BaseModel):
    id: UUID4
    label: Optional[str] = None
    journey_type: JourneyType
    purpose: InvitationPurpose = InvitationPurpose.GLOBAL_REGISTRATION
    mission_id: Optional[UUID4] = None
    required_data_categories: List[ParticipantDataCategory] = []
    organization_id: Optional[UUID4] = None
    organization_name: Optional[str] = None
    location_id: Optional[UUID4] = None
    location_name: Optional[str] = None
    status: PublicInvitationStatus
    expires_at: datetime
    max_uses: Optional[int] = None
    uses_count: int
    accept_path: Optional[str] = None
    revoked_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class PublicInvitationValidationResponse(BaseModel):
    valid: bool
    status: PublicInvitationStatus
    label: Optional[str] = None
    journey_type: JourneyType
    purpose: InvitationPurpose = InvitationPurpose.GLOBAL_REGISTRATION
    mission_id: Optional[UUID4] = None
    required_data_categories: List[ParticipantDataCategory] = []
    organization_id: Optional[UUID4] = None
    organization_name: Optional[str] = None
    location_id: Optional[UUID4] = None
    location_name: Optional[str] = None
    expires_at: datetime
    max_uses: Optional[int] = None
    uses_count: int
    requires_account: bool


class InvitationResponse(BaseModel):
    id: UUID4
    email: EmailStr
    journey_type: JourneyType
    purpose: InvitationPurpose = InvitationPurpose.GLOBAL_REGISTRATION
    mission_id: Optional[UUID4] = None
    required_data_categories: List[ParticipantDataCategory] = []
    organization_id: Optional[UUID4] = None
    organization_name: Optional[str] = None
    location_id: Optional[UUID4] = None
    location_name: Optional[str] = None
    status: InvitationStatus
    token_prefix: str
    accept_path: Optional[str] = None
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class InvitationAcceptRequest(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, min_length=3, max_length=200)
    social_name: Optional[str] = Field(default=None, max_length=200)
    cpf: Optional[str] = None
    phone: Optional[str] = None
    rg: Optional[str] = Field(default=None, max_length=30)
    birth_date: Optional[date] = None
    gender: Optional[str] = Field(default=None, max_length=30)
    city: Optional[str] = Field(default=None, min_length=2, max_length=120)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    zip_code: Optional[str] = Field(default=None, max_length=10)
    address_street: Optional[str] = Field(default=None, max_length=200)
    address_number: Optional[str] = Field(default=None, max_length=20)
    address_complement: Optional[str] = Field(default=None, max_length=120)
    address_neighborhood: Optional[str] = Field(default=None, max_length=120)
    emergency_contact_name: Optional[str] = Field(default=None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=30)
    bio: Optional[str] = Field(default=None, max_length=2000)
    avatar_base64: Optional[str] = Field(default=None, max_length=8_000_000)
    avatar_mime_type: Optional[str] = Field(default=None, max_length=40)
    privacy_consent: bool = False
    consent_version: str = "2026-01"

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: Optional[str]) -> Optional[str]:
        return normalize_cpf(value) if value else None

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else None


class RepresentativeLinkResponse(BaseModel):
    id: UUID4
    location_id: UUID4
    location_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    status: RepresentativeLinkStatus
    responsibilities: Optional[list] = None
    started_at: Optional[datetime] = None


class RepresentativeLinkUpdate(BaseModel):
    status: RepresentativeLinkStatus
    responsibilities: Optional[list] = None


class WorkflowEventCreate(BaseModel):
    stage: WorkflowStage


class WorkflowEventResponse(BaseModel):
    id: UUID4
    location_id: UUID4
    stage: WorkflowStage
    status: WorkflowStatus
    actor_user_id: Optional[UUID4] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WorkflowDecisionRequest(BaseModel):
    approve: bool
    notes: Optional[str] = Field(default=None, max_length=1000)


class DocumentResponse(BaseModel):
    id: UUID4
    owner_type: DocumentOwnerType
    owner_id: UUID4
    document_type: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: DocumentStatus
    rejection_reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    download_path: str


class DocumentReviewRequest(BaseModel):
    status: DocumentStatus = DocumentStatus.APPROVED
    rejection_reason: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: DocumentStatus) -> DocumentStatus:
        if value not in {DocumentStatus.APPROVED, DocumentStatus.REJECTED}:
            raise ValueError("Revisao deve ser APPROVED ou REJECTED.")
        return value


class ConsentCreate(BaseModel):
    consent_type: str = Field(default="PRIVACY_POLICY", max_length=40)
    policy_version: str = Field(default="2026-01", max_length=40)
    purpose: str = Field(default="Execucao de atividades operacionais", max_length=500)
    legal_basis: str = Field(default="CONSENTIMENTO", max_length=80)


class ConsentResponse(BaseModel):
    id: UUID4
    consent_type: str
    policy_version: str
    purpose: str
    legal_basis: str
    granted_at: datetime
    revoked_at: Optional[datetime] = None


class QualificationRequirementCreate(BaseModel):
    course_version_id: UUID4
    function_name: ProfessionalFunction
    is_required: bool = True
    validity_days: Optional[int] = Field(default=None, ge=1, le=3650)


class QualificationRequirementResponse(BaseModel):
    id: UUID4
    course_version_id: UUID4
    function_name: str
    is_required: bool
    validity_days: Optional[int] = None
    course_title: Optional[str] = None
    version_tag: Optional[str] = None


class QualificationIssueRequest(BaseModel):
    user_id: UUID4
    function_name: ProfessionalFunction
    validity_days: Optional[int] = Field(default=None, ge=1, le=3650)


class QualificationResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    function_name: str
    status: QualificationStatus
    certification_id: Optional[UUID4] = None
    course_version_id: Optional[UUID4] = None
    issued_at: datetime
    expires_at: Optional[datetime] = None
    suspended_reason: Optional[str] = None


class MissionApplicationCreate(BaseModel):
    mission_id: UUID4


class MissionApplicationDecision(BaseModel):
    status: ApplicationStatus
    notes: Optional[str] = Field(default=None, max_length=500)


class MissionInvitationCreate(BaseModel):
    user_ids: List[UUID4] = Field(min_length=1)
    message: Optional[str] = Field(default=None, max_length=1000)


class MissionInvitationResponse(BaseModel):
    id: UUID4
    mission_id: UUID4
    user_id: UUID4
    public_id: Optional[str] = None
    full_name: Optional[str] = None
    function_name: Optional[str] = None
    status: MissionInvitationStatus
    message: Optional[str] = None
    mission_title: Optional[str] = None
    mission_status: Optional[str] = None
    mission_city: Optional[str] = None
    mission_state: Optional[str] = None
    location_name: Optional[str] = None
    reward_amount: Optional[float] = None
    created_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None


class MissionApplicationResponse(BaseModel):
    id: UUID4
    mission_id: UUID4
    user_id: UUID4
    public_id: Optional[str] = None
    full_name: Optional[str] = None
    status: ApplicationStatus
    applied_at: datetime
    decided_at: Optional[datetime] = None
    notes: Optional[str] = None


class CourseAudienceUpdate(BaseModel):
    audience: CourseAudience


class AuditLogResponse(BaseModel):
    id: UUID4
    actor_public_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    organization_id: Optional[UUID4] = None
    details: Optional[dict] = None
    created_at: Optional[datetime] = None


class ParticipantLinkedOrganization(BaseModel):
    organization_id: UUID4
    organization_name: Optional[str] = None
    purpose: str
    status: str
    valid_from: Optional[datetime] = None


class ParticipantSummaryResponse(BaseModel):
    user_id: UUID4
    public_id: str
    full_name: str
    city: str
    state: str
    cadastral_status: ParticipantValidationStatus
    profile_completed: bool
    has_avatar: bool = False
    avatar_url: Optional[str] = None
    journeys: List[JourneyResponse] = []
    qualifications: List["QualificationResponse"] = []
    created_at: Optional[datetime] = None


class ParticipantDetailResponse(ParticipantSummaryResponse):
    social_name: Optional[str] = None
    cpf_masked: str
    phone_masked: str
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    organizations: List[ParticipantLinkedOrganization] = []


class ParticipantValidationCreate(BaseModel):
    scope: ParticipantValidationScope
    status: ParticipantValidationStatus
    notes: Optional[str] = Field(default=None, max_length=2000)
    organization_id: Optional[UUID4] = None


class ParticipantValidationResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    scope: ParticipantValidationScope
    status: ParticipantValidationStatus
    reviewer_user_id: Optional[UUID4] = None
    reviewer_public_id: Optional[str] = None
    organization_id: Optional[UUID4] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class RegistrationDraftUpsert(BaseModel):
    current_step: int = Field(default=1, ge=1, le=30)
    data: Dict[str, Any] = Field(default_factory=dict)


class RegistrationDraftResponse(BaseModel):
    status: RegistrationDraftStatus
    current_step: int
    data: Dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime
    updated_at: Optional[datetime] = None


AccountResponse.model_rebuild()
