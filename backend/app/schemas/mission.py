from pydantic import BaseModel, UUID4, ConfigDict
from typing import Optional, Any
from datetime import datetime
from app.models.mission import MissionType, MissionStatus

class MissionBase(BaseModel):
    title: str
    mission_type: MissionType = MissionType.VISTORIA
    status: MissionStatus = MissionStatus.OPEN
    city: str
    state: str
    reward_amount: float = 150.00
    deadline: Optional[datetime] = None
    checklist: Optional[Any] = None
    required_function: Optional[str] = None

class MissionCreate(MissionBase):
    location_id: Optional[UUID4] = None
    assigned_user_id: Optional[UUID4] = None

class MissionResponse(MissionBase):
    id: UUID4
    location_id: Optional[UUID4] = None
    assigned_user_id: Optional[UUID4] = None
    created_at: datetime
    location_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
