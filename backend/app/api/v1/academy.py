from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.core.deps import get_db, get_current_active_user
from app.models.user import User
from app.schemas.academy import (
    CourseCreate,
    CourseResponse,
    ModuleCreate,
    ModuleResponse,
    LessonCreate,
    LessonResponse,
    CertificationResponse,
)
from app.services import academy_service

router = APIRouter(prefix="/academy", tags=["Academy"])

@router.get("/courses", response_model=List[CourseResponse])
async def list_courses(
    published_only: bool = False,
    organization_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    courses = await academy_service.list_courses(
        db, organization_id=organization_id, published_only=published_only
    )
    return [CourseResponse.model_validate(c) for c in courses]

@router.post("/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    course_in: CourseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    course = await academy_service.create_course(db, course_in)
    return CourseResponse.model_validate(course)

@router.get("/courses/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    course = await academy_service.get_course_by_id(db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso não encontrado.")
    return CourseResponse.model_validate(course)

@router.post("/versions/{version_id}/modules", response_model=ModuleResponse, status_code=status.HTTP_201_CREATED)
async def create_module(
    version_id: str,
    module_in: ModuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    mod = await academy_service.create_module(db, version_id, module_in)
    return ModuleResponse.model_validate(mod)

@router.post("/modules/{module_id}/lessons", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson(
    module_id: str,
    lesson_in: LessonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    lesson = await academy_service.create_lesson(db, module_id, lesson_in)
    return LessonResponse.model_validate(lesson)

@router.post("/versions/{version_id}/certify", response_model=CertificationResponse)
async def certify_user(
    version_id: UUID,
    score: float = 100.0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    cert = await academy_service.issue_certification(
        db, user_id=current_user.id, course_version_id=version_id, score=score
    )
    # Return formatted response
    certs = await academy_service.get_user_certifications(db, current_user.id)
    for c in certs:
        if str(c["id"]) == str(cert.id):
            return CertificationResponse.model_validate(c)
    return CertificationResponse.model_validate(cert)

@router.get("/my-certifications", response_model=List[CertificationResponse])
async def get_my_certifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    certs = await academy_service.get_user_certifications(db, current_user.id)
    return [CertificationResponse.model_validate(c) for c in certs]

@router.post("/seed", status_code=status.HTTP_200_OK)
async def seed_academy(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await academy_service.seed_default_courses(db)
    return {"status": "ok", "message": "Cursos padrão da Academy semeados com sucesso."}
