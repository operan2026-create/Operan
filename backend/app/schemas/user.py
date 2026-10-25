from pydantic import BaseModel, UUID4, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional
from app.models.user import UserStatus

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

    model_config = ConfigDict(from_attributes=True)
