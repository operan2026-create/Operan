import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academy import Certification, CertificationStatus, CourseVersion
from app.models.participant import (
    JourneyEnrollment,
    JourneyStatus,
    JourneyType,
    ProfessionalQualification,
    QualificationRequirement,
    QualificationStatus,
)
from app.models.user import User
from app.schemas.participant import (
    QualificationIssueRequest,
    QualificationRequirementCreate,
    QualificationRequirementResponse,
    QualificationResponse,
)
from app.services import audit_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _response(q: ProfessionalQualification) -> QualificationResponse:
    return QualificationResponse(
        id=q.id,
        user_id=q.user_id,
        function_name=q.function_name,
        status=q.status,
        certification_id=q.certification_id,
        course_version_id=q.course_version_id,
        issued_at=q.issued_at,
        expires_at=q.expires_at,
        suspended_reason=q.suspended_reason,
    )


async def list_requirements(
    db: AsyncSession, function_name: Optional[str] = None
) -> list[QualificationRequirementResponse]:
    query = (
        select(QualificationRequirement)
        .options(
            selectinload(QualificationRequirement.course_version).selectinload(
                CourseVersion.course
            )
        )
        .order_by(QualificationRequirement.function_name.asc())
    )
    if function_name:
        query = query.where(QualificationRequirement.function_name == function_name.upper())
    rows = (await db.execute(query)).scalars().all()
    output = []
    for req in rows:
        version = req.course_version
        output.append(
            QualificationRequirementResponse(
                id=req.id,
                course_version_id=req.course_version_id,
                function_name=req.function_name,
                is_required=req.is_required,
                validity_days=req.validity_days,
                course_title=version.course.title if version and version.course else None,
                version_tag=version.version_tag if version else None,
            )
        )
    return output


async def create_requirement(
    db: AsyncSession,
    admin: User,
    payload: QualificationRequirementCreate,
    request: Optional[Request] = None,
) -> QualificationRequirementResponse:
    version = (
        (await db.execute(select(CourseVersion).where(CourseVersion.id == payload.course_version_id)))
        .scalars()
        .first()
    )
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Versao de curso nao encontrada."
        )
    existing = (
        (
            await db.execute(
                select(QualificationRequirement).where(
                    QualificationRequirement.course_version_id == payload.course_version_id,
                    QualificationRequirement.function_name == payload.function_name.value,
                )
            )
        )
        .scalars()
        .first()
    )
    if existing:
        existing.is_required = payload.is_required
        existing.validity_days = payload.validity_days
        requirement = existing
    else:
        requirement = QualificationRequirement(
            course_version_id=payload.course_version_id,
            function_name=payload.function_name.value,
            is_required=payload.is_required,
            validity_days=payload.validity_days,
        )
        db.add(requirement)
    await db.flush()
    audit_service.record(
        db,
        action="qualification_requirement.saved",
        entity_type="QualificationRequirement",
        actor=admin,
        entity_id=str(requirement.id),
        details={
            "function_name": payload.function_name.value,
            "course_version_id": str(payload.course_version_id),
        },
        request=request,
    )
    await db.commit()
    await db.refresh(requirement)
    return (
        await list_requirements(db, payload.function_name.value)
    )[0]


async def _user_certifications(
    db: AsyncSession, user_id: uuid.UUID
) -> list[Certification]:
    result = await db.execute(
        select(Certification).where(
            Certification.user_id == user_id,
            Certification.status == CertificationStatus.VALID,
        )
    )
    return list(result.scalars().all())


async def has_valid_qualification(
    db: AsyncSession, user_id: uuid.UUID, function_name: str
) -> bool:
    qualification = (
        (
            await db.execute(
                select(ProfessionalQualification).where(
                    ProfessionalQualification.user_id == user_id,
                    ProfessionalQualification.function_name == function_name.upper(),
                    ProfessionalQualification.status == QualificationStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .first()
    )
    if not qualification:
        return False
    if qualification.expires_at and _aware(qualification.expires_at) <= _now():
        qualification.status = QualificationStatus.EXPIRED
        await db.commit()
        return False
    return True


async def issue_qualification(
    db: AsyncSession,
    admin: User,
    payload: QualificationIssueRequest,
    request: Optional[Request] = None,
) -> QualificationResponse:
    target = (
        (await db.execute(select(User).where(User.id == payload.user_id))).scalars().first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")
    journey = (
        (
            await db.execute(
                select(JourneyEnrollment).where(
                    JourneyEnrollment.user_id == target.id,
                    JourneyEnrollment.journey_type == JourneyType.PROFESSIONALS,
                    JourneyEnrollment.status == JourneyStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .first()
    )
    if not journey:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O usuario nao possui jornada profissional ativa.",
        )

    requirements = (
        await db.execute(
            select(QualificationRequirement).where(
                QualificationRequirement.function_name == payload.function_name.value,
                QualificationRequirement.is_required.is_(True),
            )
        )
    ).scalars().all()
    if not requirements:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nenhum requisito de curso configurado para esta funcao.",
        )

    certifications = await _user_certifications(db, target.id)
    cert_by_version = {cert.course_version_id: cert for cert in certifications}
    missing = [
        req.course_version_id
        for req in requirements
        if req.course_version_id not in cert_by_version
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Certificacoes obrigatorias ausentes para a funcao: "
                + ", ".join(str(item) for item in missing)
            ),
        )

    latest_cert = max(
        (cert_by_version[req.course_version_id] for req in requirements),
        key=lambda cert: cert.issued_at or _now(),
    )
    validity_days = payload.validity_days
    if validity_days is None:
        configured = [req.validity_days for req in requirements if req.validity_days]
        validity_days = max(configured) if configured else None
    expires_at = _now() + timedelta(days=validity_days) if validity_days else None

    qualification = (
        (
            await db.execute(
                select(ProfessionalQualification).where(
                    ProfessionalQualification.user_id == target.id,
                    ProfessionalQualification.function_name == payload.function_name.value,
                )
            )
        )
        .scalars()
        .first()
    )
    if qualification:
        qualification.status = QualificationStatus.ACTIVE
        qualification.certification_id = latest_cert.id
        qualification.course_version_id = latest_cert.course_version_id
        qualification.issued_at = _now()
        qualification.expires_at = expires_at
        qualification.issued_by_user_id = admin.id
        qualification.suspended_reason = None
    else:
        qualification = ProfessionalQualification(
            user_id=target.id,
            function_name=payload.function_name.value,
            status=QualificationStatus.ACTIVE,
            certification_id=latest_cert.id,
            course_version_id=latest_cert.course_version_id,
            issued_at=_now(),
            expires_at=expires_at,
            issued_by_user_id=admin.id,
        )
        db.add(qualification)
    await db.flush()
    audit_service.record(
        db,
        action="qualification.issued",
        entity_type="ProfessionalQualification",
        actor=admin,
        entity_id=str(qualification.id),
        details={
            "user_id": str(target.id),
            "function_name": payload.function_name.value,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(qualification)
    return _response(qualification)


async def list_qualifications(
    db: AsyncSession, user_id: uuid.UUID
) -> list[QualificationResponse]:
    quals = (
        await db.execute(
            select(ProfessionalQualification)
            .where(ProfessionalQualification.user_id == user_id)
            .order_by(ProfessionalQualification.function_name.asc())
        )
    ).scalars().all()
    for q in quals:
        if (
            q.expires_at
            and _aware(q.expires_at) <= _now()
            and q.status == QualificationStatus.ACTIVE
        ):
            q.status = QualificationStatus.EXPIRED
    await db.commit()
    return [_response(q) for q in quals]
