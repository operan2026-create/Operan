from pydantic import BaseModel, UUID4, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.models.academy import CourseStatus, LessonContentType, CertificationStatus

# Lesson Schemas
class LessonBase(BaseModel):
    title: str
    content_type: LessonContentType = LessonContentType.TEXT
    content: Optional[str] = None
    storage_key: Optional[str] = None
    duration_minutes: int = 5
    order_index: int = 0

class LessonCreate(LessonBase):
    pass

class LessonResponse(LessonBase):
    id: UUID4
    module_id: UUID4

    model_config = ConfigDict(from_attributes=True)

# Module Schemas
class ModuleBase(BaseModel):
    title: str
    order_index: int = 0

class ModuleCreate(ModuleBase):
    pass

class ModuleResponse(ModuleBase):
    id: UUID4
    course_version_id: UUID4
    lessons: List[LessonResponse] = []

    model_config = ConfigDict(from_attributes=True)

# CourseVersion Schemas
class CourseVersionBase(BaseModel):
    version_tag: str = "v1.0"
    is_active: bool = True

class CourseVersionCreate(CourseVersionBase):
    pass

class CourseVersionResponse(CourseVersionBase):
    id: UUID4
    course_id: UUID4
    created_at: datetime
    modules: List[ModuleResponse] = []

    model_config = ConfigDict(from_attributes=True)

# Course Schemas
class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: CourseStatus = CourseStatus.DRAFT
    organization_id: Optional[UUID4] = None

class CourseCreate(CourseBase):
    pass

class CourseResponse(CourseBase):
    id: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = None
    versions: List[CourseVersionResponse] = []

    model_config = ConfigDict(from_attributes=True)

# Certification Schemas (Passaporte Operacional)
class CertificationResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    course_version_id: UUID4
    status: CertificationStatus
    score: Optional[float] = None
    issued_at: datetime
    expires_at: Optional[datetime] = None
    course_title: Optional[str] = None
    version_tag: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
