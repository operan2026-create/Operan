import uuid
import enum
from sqlalchemy import Column, String, Integer, Boolean, Enum, DateTime, ForeignKey, Numeric, Float, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.security.encrypted_types import EncryptedString

class LocationStatus(str, enum.Enum):
    DECLARADO = "DECLARADO"     # 🟡 Declarado pelo representante ou parceiro
    VISTORIADO = "VISTORIADO"   # 🔵 Vistoriador habilitado foi in loco e validou
    CONFIRMADO = "CONFIRMADO"   # 🟢 Reconfirmado especificamente para uma operação

class ProfessionalAvailability(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    IN_MISSION = "IN_MISSION"

class Location(Base):
    __tablename__ = "locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    city = Column(String, nullable=False, index=True)
    state = Column(String(2), nullable=False, index=True)
    neighborhood = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)
    
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    total_rooms = Column(Integer, default=10, nullable=False)
    total_capacity = Column(Integer, default=300, nullable=False)
    has_accessibility = Column(Boolean, default=True, nullable=False)
    has_air_conditioning = Column(Boolean, default=True, nullable=False)
    
    status = Column(Enum(LocationStatus), default=LocationStatus.DECLARADO, nullable=False)
    reliability_score = Column(Numeric(5, 2), default=100.0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization")
    missions = relationship("Mission", back_populates="location")

class Professional(Base):
    __tablename__ = "professionals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    full_name = Column(EncryptedString, nullable=False)
    cpf_hash = Column(String, unique=True, index=True, nullable=False)
    cpf_encrypted = Column(String, nullable=False)
    phone_encrypted = Column(String, nullable=False)
    
    city = Column(EncryptedString, nullable=False)
    state = Column(EncryptedString, nullable=False)
    operational_radius_km = Column(Integer, default=30, nullable=False)
    
    availability_status = Column(Enum(ProfessionalAvailability), default=ProfessionalAvailability.AVAILABLE, nullable=False)
    reputation_score = Column(Numeric(5, 2), default=98.5, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")
