import uuid
import enum
from sqlalchemy import Column, String, Text, Integer, Boolean, Enum, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class CourseStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"

class LessonContentType(str, enum.Enum):
    VIDEO = "VIDEO"
    PDF = "PDF"
    TEXT = "TEXT"

class CertificationStatus(str, enum.Enum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    status = Column(Enum(CourseStatus), default=CourseStatus.DRAFT, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    versions = relationship("CourseVersion", back_populates="course", cascade="all, delete-orphan")
    organization = relationship("Organization")

class CourseVersion(Base):
    __tablename__ = "course_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    version_tag = Column(String, nullable=False, default="v1.0")
    content_hash = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    course = relationship("Course", back_populates="versions")
    modules = relationship("Module", back_populates="course_version", cascade="all, delete-orphan", order_by="Module.order_index")
    certifications = relationship("Certification", back_populates="course_version")

class Module(Base):
    __tablename__ = "modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    course_version_id = Column(UUID(as_uuid=True), ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)

    # Relationships
    course_version = relationship("CourseVersion", back_populates="modules")
    lessons = relationship("Lesson", back_populates="module", cascade="all, delete-orphan", order_by="Lesson.order_index")

class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    module_id = Column(UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    content_type = Column(Enum(LessonContentType), default=LessonContentType.TEXT, nullable=False)
    content = Column(Text, nullable=True)
    storage_key = Column(String, nullable=True)
    duration_minutes = Column(Integer, default=5, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)

    # Relationships
    module = relationship("Module", back_populates="lessons")

class Certification(Base):
    __tablename__ = "certifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_version_id = Column(UUID(as_uuid=True), ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(CertificationStatus), default=CertificationStatus.VALID, nullable=False)
    score = Column(Numeric(5, 2), nullable=True)
    
    issued_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")
    course_version = relationship("CourseVersion", back_populates="certifications")
