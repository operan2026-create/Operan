from pydantic import BaseModel, UUID4, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.models.network import LocationStatus, ProfessionalAvailability

class LocationBase(BaseModel):
    name: str
    address: str
    city: str
    state: str
    neighborhood: Optional[str] = None
    zip_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    total_rooms: int = 10
    total_capacity: int = 300
    has_accessibility: bool = True
    has_air_conditioning: bool = True
    status: LocationStatus = LocationStatus.DECLARADO
    reliability_score: float = 100.0

class LocationCreate(LocationBase):
    organization_id: Optional[UUID4] = None

class LocationResponse(LocationBase):
    id: UUID4
    organization_id: Optional[UUID4] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ProfessionalBase(BaseModel):
    full_name: str
    city: str
    state: str
    operational_radius_km: int = 30
    availability_status: ProfessionalAvailability = ProfessionalAvailability.AVAILABLE
    reputation_score: float = 98.5

class ProfessionalCreate(ProfessionalBase):
    user_id: UUID4
    cpf: str
    phone: str

class ProfessionalResponse(ProfessionalBase):
    id: UUID4
    user_id: UUID4
    public_id: Optional[str] = None
    qualifications: List[str] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
