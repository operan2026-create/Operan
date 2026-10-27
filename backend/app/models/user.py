import uuid
from sqlalchemy import Column, String, Enum, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum

class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    BLOCKED = "BLOCKED"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    public_id = Column(String, unique=True, index=True, nullable=False)
    
    # Encrypted Email Fields
    email_hash = Column(String, unique=True, index=True, nullable=False)
    email_encrypted = Column(String, nullable=False)
    
    password_hash = Column(String, nullable=False)
    
    status = Column(Enum(UserStatus), default=UserStatus.PENDING, nullable=False)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    # Reserved for a future MFA flow. It is not read or written by the current
    # authentication code and must be encrypted before any real secret is stored.
    mfa_secret = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")

    @property
    def email(self) -> str:
        if not self.email_encrypted:
            return ""
        from app.security.encryption import crypto_manager
        return crypto_manager.decrypt_data(self.email_encrypted)
