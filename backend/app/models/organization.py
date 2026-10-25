import uuid
from sqlalchemy import Column, String, Enum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum

class OrganizationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    public_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    
    # Encrypted fields
    cnpj_hash = Column(String, unique=True, index=True, nullable=True)
    cnpj_encrypted = Column(String, nullable=True)
    
    status = Column(Enum(OrganizationStatus), default=OrganizationStatus.ACTIVE, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    memberships = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")

    @property
    def cnpj(self) -> str | None:
        if not self.cnpj_encrypted:
            return None
        from app.security.encryption import crypto_manager
        return crypto_manager.decrypt_data(self.cnpj_encrypted)
