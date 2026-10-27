import uuid
import enum
from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Numeric, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class MissionType(str, enum.Enum):
    CAPTACAO = "CAPTACAO"
    VISTORIA = "VISTORIA"
    RECERTIFICACAO = "RECERTIFICACAO"
    CONFIRMACAO = "CONFIRMACAO"
    APOIO_OPERACIONAL = "APOIO_OPERACIONAL"

class MissionStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class Mission(Base):
    __tablename__ = "missions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String, nullable=False)
    mission_type = Column(Enum(MissionType), default=MissionType.VISTORIA, nullable=False)
    status = Column(Enum(MissionStatus), default=MissionStatus.OPEN, nullable=False)
    
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    city = Column(String, nullable=False)
    state = Column(String(2), nullable=False)
    reward_amount = Column(Numeric(10, 2), default=150.00, nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=True)
    
    checklist = Column(JSON, nullable=True)
    required_function = Column(String(40), nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    location = relationship("Location", back_populates="missions")
    assigned_user = relationship("User")
