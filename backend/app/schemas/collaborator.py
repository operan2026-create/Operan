from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.network import ProfessionalAvailability

class CollaboratorRegisterRequest(BaseModel):
    # User Account info
    email: EmailStr
    password: str
    
    # Professional info
    full_name: str
    cpf: str
    phone: str
    city: str
    state: str
    operational_radius_km: int = 30

class CollaboratorRegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    public_id: str
    full_name: str
    city: str
    state: str
    status: str
