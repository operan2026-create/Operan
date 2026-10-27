from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.core.deps import get_db, get_current_user_context, require_admin, UserContext
from app.models.academy import CourseAudience, CourseStatus
from app.schemas.academy import (
    CourseCreate,
    CourseResponse,
    ModuleCreate,
    ModuleResponse,
    LessonCreate,
    LessonResponse,
    LessonCompletionResponse,
    CertificationResponse,
)
from app.services import academy_service

router = APIRouter(prefix="/academy", tags=["Academy"])


def _course_audiences(context: UserContext):
    if context.is_admin or context.is_client:
        return None
    if context.is_participant:
        audiences = []
        if context.is_professional or context.professional is not None:
            audiences.append(CourseAudience.PROFESSIONALS)
        if context.is_representative:
            audiences.append(CourseAudience.LOCATIONS)
        return audiences or [CourseAudience.PROFESSIONALS]
    return []


def _course_scope(context: UserContext, published_only: bool):
    """Returns (org_ids, published_only, global_published_only) for the actor."""
    if context.is_admin:
        return None, published_only, False
    if context.is_client:
        return context.client_organization_ids, published_only, True
    if context.is_participant:
        # Cursos publicados formam o catálogo público da Academia.
        # Rascunhos e cursos arquivados permanecem ocultos.
        return None, True, False
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acesso negado: usuário sem perfil de acesso à Academia.",
    )


@router.get("/courses", response_model=List[CourseResponse])
async def list_courses(
    published_only: bool = False,
    organization_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    org_ids, published_only, global_published_only = _course_scope(context, published_only)
    audiences = _course_audiences(context)

    courses = await academy_service.list_courses(
        db,
        organization_ids=org_ids,
        published_only=published_only,
        global_published_only=global_published_only,
        audiences=audiences,
    )

    if context.is_admin and organization_id is not None:
        courses = [c for c in courses if c.organization_id == organization_id]

    return [CourseResponse.model_validate(c) for c in courses]


@router.post("/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    course_in: CourseCreate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Administradores ou gestores de organização cliente podem criar cursos.",
        )

    if not context.is_admin:
        if not context.primary_organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cliente não possui organização ativa para vincular o curso.",
            )
        course_in.organization_id = context.primary_organization_id

    course = await academy_service.create_course(db, course_in)
    return CourseResponse.model_validate(course)


@router.get("/courses/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    org_ids, published_only, global_published_only = _course_scope(context, False)
    audiences = _course_audiences(context)

    course = await academy_service.get_course_by_id(
        db,
        course_id,
        organization_ids=org_ids,
        published_only=published_only,
        global_published_only=global_published_only,
        audiences=audiences,
    )
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso não encontrado.")
    return CourseResponse.model_validate(course)


@router.post("/versions/{version_id}/modules", response_model=ModuleResponse, status_code=status.HTTP_201_CREATED)
async def create_module(
    version_id: str,
    module_in: ModuleCreate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    mod = await academy_service.create_module(db, version_id, module_in)
    return ModuleResponse.model_validate(mod)


@router.post("/modules/{module_id}/lessons", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson(
    module_id: str,
    lesson_in: LessonCreate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    lesson = await academy_service.create_lesson(db, module_id, lesson_in)
    return LessonResponse.model_validate(lesson)


@router.post("/lessons/{lesson_id}/complete", response_model=LessonCompletionResponse)
async def complete_lesson(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_participant and not context.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas participantes podem registrar conclusão de aulas.",
        )

    lesson = await academy_service.get_lesson_with_course(db, lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula não encontrada.")

    version = lesson.module.course_version
    course = version.course

    if course.status != CourseStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aula pertence a curso não publicado.",
        )

    completion = await academy_service.mark_lesson_complete(db, context.user.id, lesson_id)
    return LessonCompletionResponse.model_validate(completion)


@router.post("/versions/{version_id}/certify", response_model=CertificationResponse)
async def certify_user(
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_participant and not context.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas participantes podem obter certificação.",
        )

    version = await academy_service.get_version(db, version_id)
    if not version or not version.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Versão de curso não encontrada ou inativa.",
        )

    course = version.course
    if course.status != CourseStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificação disponível apenas para cursos publicados.",
        )

    total_lessons = await academy_service.count_lessons_for_version(db, version_id)
    if total_lessons == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Curso sem aulas avaliáveis; certificação não pode ser emitida.",
        )

    completed = await academy_service.count_user_completions_for_version(
        db, context.user.id, version_id
    )
    if completed < total_lessons:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Conclusão incompleta: "
                f"{completed} de {total_lessons} aulas concluídas."
            ),
        )

    cert = await academy_service.issue_certification(
        db, user_id=context.user.id, course_version_id=version_id
    )
    certs = await academy_service.get_user_certifications(db, context.user.id)
    for c in certs:
        if str(c["id"]) == str(cert.id):
            return CertificationResponse.model_validate(c)
    return CertificationResponse.model_validate(cert)


@router.get("/my-certifications", response_model=List[CertificationResponse])
async def get_my_certifications(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    certs = await academy_service.get_user_certifications(db, context.user.id)
    return [CertificationResponse.model_validate(c) for c in certs]


@router.post("/seed", status_code=status.HTTP_200_OK)
async def seed_academy(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    await academy_service.seed_default_courses(db)
    return {"status": "ok", "message": "Cursos padrão da Academy semeados com sucesso."}
