from pydantic import BaseModel, UUID4, ConfigDict
from typing import Optional

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_system: bool = False

class RoleCreate(RoleBase):
    pass

class RoleResponse(RoleBase):
    id: UUID4

    model_config = ConfigDict(from_attributes=True)
