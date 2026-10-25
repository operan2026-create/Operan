from pydantic import BaseModel, UUID4, ConfigDict
from datetime import datetime
from typing import Optional
from app.models.membership import MembershipStatus

class MembershipBase(BaseModel):
    user_id: UUID4
    organization_id: UUID4
    role_id: UUID4
    status: MembershipStatus = MembershipStatus.INVITED

class MembershipCreate(MembershipBase):
    pass

class MembershipResponse(MembershipBase):
    id: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
