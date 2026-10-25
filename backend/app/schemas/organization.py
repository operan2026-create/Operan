from pydantic import BaseModel, UUID4, ConfigDict
from datetime import datetime
from typing import Optional
from app.models.organization import OrganizationStatus

class OrganizationBase(BaseModel):
    name: str
    status: OrganizationStatus = OrganizationStatus.ACTIVE

class OrganizationCreate(OrganizationBase):
    cnpj: Optional[str] = None # Will be hashed and encrypted before saving

class OrganizationResponse(OrganizationBase):
    id: UUID4
    public_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
