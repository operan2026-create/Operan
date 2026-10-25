from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.academy import Course, CourseVersion, Module, Lesson, Certification, CourseStatus, CertificationStatus
from app.schemas.academy import CourseCreate, ModuleCreate, LessonCreate

async def create_course(db: AsyncSession, course_in: CourseCreate) -> Course:
    course = Course(
        title=course_in.title,
        description=course_in.description,
        thumbnail_url=course_in.thumbnail_url,
        status=course_in.status,
        organization_id=course_in.organization_id,
    )
    db.add(course)
    await db.flush()

    # Automatically create v1.0 version for this course
    version = CourseVersion(
        course_id=course.id,
        version_tag="v1.0",
        is_active=True,
    )
    db.add(version)
    await db.commit()
    await db.refresh(course)
    return await get_course_by_id(db, str(course.id))

async def list_courses(
    db: AsyncSession,
    organization_id: Optional[UUID] = None,
    published_only: bool = False,
) -> List[Course]:
    query = (
        select(Course)
        .options(
            selectinload(Course.versions)
            .selectinload(CourseVersion.modules)
            .selectinload(Module.lessons)
        )
        .order_by(Course.created_at.desc())
    )
    if published_only:
        query = query.where(Course.status == CourseStatus.PUBLISHED)
    if organization_id:
        query = query.where((Course.organization_id == organization_id) | (Course.organization_id.is_(None)))

    result = await db.execute(query)
    return list(result.scalars().all())

async def get_course_by_id(db: AsyncSession, course_id: str) -> Optional[Course]:
    query = (
        select(Course)
        .where(Course.id == course_id)
        .options(
            selectinload(Course.versions)
            .selectinload(CourseVersion.modules)
            .selectinload(Module.lessons)
        )
    )
    result = await db.execute(query)
    return result.scalars().first()

async def create_module(db: AsyncSession, version_id: str, module_in: ModuleCreate) -> Module:
    module = Module(
        course_version_id=version_id,
        title=module_in.title,
        order_index=module_in.order_index,
    )
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return module

async def create_lesson(db: AsyncSession, module_id: str, lesson_in: LessonCreate) -> Lesson:
    lesson = Lesson(
        module_id=module_id,
        title=lesson_in.title,
        content_type=lesson_in.content_type,
        content=lesson_in.content,
        storage_key=lesson_in.storage_key,
        duration_minutes=lesson_in.duration_minutes,
        order_index=lesson_in.order_index,
    )
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    return lesson

async def issue_certification(
    db: AsyncSession,
    user_id: UUID,
    course_version_id: UUID,
    score: float = 100.0,
) -> Certification:
    # Check if already certified for this version
    query = select(Certification).where(
        Certification.user_id == user_id,
        Certification.course_version_id == course_version_id,
    )
    res = await db.execute(query)
    cert = res.scalars().first()
    if cert:
        return cert

    cert = Certification(
        user_id=user_id,
        course_version_id=course_version_id,
        status=CertificationStatus.VALID,
        score=score,
    )
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return cert

async def get_user_certifications(db: AsyncSession, user_id: UUID) -> List[dict]:
    query = (
        select(Certification)
        .where(Certification.user_id == user_id)
        .options(
            selectinload(Certification.course_version).selectinload(CourseVersion.course)
        )
        .order_by(Certification.issued_at.desc())
    )
    res = await db.execute(query)
    certs = res.scalars().all()
    output = []
    for c in certs:
        output.append({
            "id": c.id,
            "user_id": c.user_id,
            "course_version_id": c.course_version_id,
            "status": c.status,
            "score": float(c.score) if c.score else None,
            "issued_at": c.issued_at,
            "expires_at": c.expires_at,
            "course_title": c.course_version.course.title if c.course_version and c.course_version.course else "Curso OPERAN",
            "version_tag": c.course_version.version_tag if c.course_version else "v1.0",
        })
    return output

async def seed_default_courses(db: AsyncSession):
    """Seed initial foundational courses for OPERAN Academy if empty."""
    res = await db.execute(select(Course))
    if res.scalars().first():
        return # already seeded

    # 1. Trilha 01: Formação OPERAN Base
    course1 = Course(
        title="Formação Base OPERAN 101",
        description="Fundamentos operacionais, ética, sigilo, proteção de dados (LGPD) e protocolos de segurança em concursos e grandes avaliações.",
        thumbnail_url="https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=600&auto=format&fit=crop&q=80",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course1)
    await db.flush()

    v1 = CourseVersion(course_id=course1.id, version_tag="v1.0", is_active=True)
    db.add(v1)
    await db.flush()

    m1 = Module(course_version_id=v1.id, title="Módulo 1: Introdução e Ética Operacional", order_index=1)
    db.add(m1)
    await db.flush()

    db.add(Lesson(
        module_id=m1.id,
        title="1.1 Visão Geral do Ecossistema OPERAN",
        content_type="TEXT",
        content="Bem-vindo à OPERAN. Você agora faz parte da maior rede de infraestrutura e aplicação operacional do país. Nesta aula, entenderemos a responsabilidade e os padrões de excelência operacional esperados de todos os colaboradores.",
        duration_minutes=8,
        order_index=1,
    ))
    db.add(Lesson(
        module_id=m1.id,
        title="1.2 Sigilo, LGPD e Tratamento de Dados",
        content_type="TEXT",
        content="Como colaborador OPERAN, você lida com documentos sigilosos, listas de presença e dados sensíveis de candidatos. É estritamente proibido fotografar cadernos de prova, crachás ou divulgar ocorrências operacionais sem autorização expressa da Coordenação.",
        duration_minutes=12,
        order_index=2,
    ))

    # 2. Trilha 02: Fiscal de Sala
    course2 = Course(
        title="Habilitação Operacional: Fiscal de Sala",
        description="Treinamento oficial para atuação em sala de prova: conferência de documentos, coleta de digitais, aplicação de detectores de metal e ata de sala.",
        thumbnail_url="https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=600&auto=format&fit=crop&q=80",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course2)
    await db.flush()

    v2 = CourseVersion(course_id=course2.id, version_tag="v1.0", is_active=True)
    db.add(v2)
    await db.flush()

    m2 = Module(course_version_id=v2.id, title="Módulo 1: Procedimentos de Aplicação", order_index=1)
    db.add(m2)
    await db.flush()

    db.add(Lesson(
        module_id=m2.id,
        title="1.1 Abertura de Portões e Recepção de Candidatos",
        content_type="TEXT",
        content="Protocolo rigoroso de conferência de documento original com foto, checagem do cartão de confirmação e orientação dos candidatos até suas respectivas carteiras.",
        duration_minutes=15,
        order_index=1,
    ))
    db.add(Lesson(
        module_id=m2.id,
        title="1.2 Rompimento de Lacres e Malotes",
        content_type="TEXT",
        content="O rompimento do malote de provas deve ser testemunhado por pelo menos 2 candidatos que assinarão a ata de abertura na presença do Chefe de Sala.",
        duration_minutes=10,
        order_index=2,
    ))

    await db.commit()
