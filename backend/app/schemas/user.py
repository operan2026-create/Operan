from pydantic import BaseModel, UUID4, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional, List
from app.models.user import UserStatus

class MembershipInfo(BaseModel):
    id: UUID4
    organization_id: UUID4
    organization_name: Optional[str] = None
    role_id: UUID4
    role_name: str
    status: str

    model_config = ConfigDict(from_attributes=True)

class ProfessionalInfo(BaseModel):
    id: UUID4
    full_name: str
    city: str
    state: str
    operational_radius_km: int
    availability_status: str
    reputation_score: float

    model_config = ConfigDict(from_attributes=True)

class UserBase(BaseModel):
    email: EmailStr
    status: UserStatus = UserStatus.PENDING

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: UUID4
    public_id: str
    mfa_enabled: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    primary_role: str = "PARTICIPANT"
    roles: List[str] = []
    memberships: List[MembershipInfo] = []
    professional: Optional[ProfessionalInfo] = None

    model_config = ConfigDict(from_attributes=True)

