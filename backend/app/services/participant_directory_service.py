import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import UserContext
from app.models.participant import (
    JourneyEnrollment,
    ParticipantClientLink,
    ParticipantClientLinkStatus,
    ParticipantValidationEvent,
    ParticipantValidationScope,
    PersonProfile,
    ProfessionalQualification,
)
from app.models.user import User
from app.schemas.participant import (
    JourneyResponse,
    ParticipantDetailResponse,
    ParticipantLinkedOrganization,
    ParticipantSummaryResponse,
    ParticipantValidationCreate,
    ParticipantValidationResponse,
    QualificationResponse,
    mask_cpf,
    mask_phone,
)
from app.security.encryption import crypto_manager
from app.services import audit_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _avatar_url(profile: PersonProfile) -> Optional[str]:
    if not profile.avatar_data:
        return None
    base = f"/api/v1/participants/{profile.user_id}/avatar"
    if profile.avatar_updated_at:
        return f"{base}?v={int(profile.avatar_updated_at.timestamp())}"
    return base


def _linked_user_ids(organization_ids: list[uuid.UUID]):
    return select(ParticipantClientLink.user_id).where(
        ParticipantClientLink.organization_id.in_(organization_ids),
        ParticipantClientLink.status == ParticipantClientLinkStatus.ACTIVE,
    )


def _scope_query(context: UserContext):
    query = select(PersonProfile).options(selectinload(PersonProfile.user))
    if context.is_admin:
        return query
    organization_ids = context.client_organization_ids
    if not organization_ids:
        return query.where(PersonProfile.id.is_(None))
    return query.where(PersonProfile.user_id.in_(_linked_user_ids(organization_ids)))


async def _bulk_journeys(
    db: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[JourneyEnrollment]]:
    if not user_ids:
        return {}
    rows = (
        await db.execute(
            select(JourneyEnrollment)
            .where(JourneyEnrollment.user_id.in_(user_ids))
            .order_by(JourneyEnrollment.created_at.asc())
        )
    ).scalars().all()
    grouped: dict[uuid.UUID, list[JourneyEnrollment]] = {}
    for row in rows:
        grouped.setdefault(row.user_id, []).append(row)
    return grouped


async def _bulk_qualifications(
    db: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[QualificationResponse]]:
    if not user_ids:
        return {}
    rows = (
        await db.execute(
            select(ProfessionalQualification).where(
                ProfessionalQualification.user_id.in_(user_ids)
            )
        )
    ).scalars().all()
    grouped: dict[uuid.UUID, list[QualificationResponse]] = {}
    for row in rows:
        grouped.setdefault(row.user_id, []).append(
            QualificationResponse(
                id=row.id,
                user_id=row.user_id,
                function_name=row.function_name,
                status=row.status,
                certification_id=row.certification_id,
                course_version_id=row.course_version_id,
                issued_at=row.issued_at,
                expires_at=row.expires_at,
                suspended_reason=row.suspended_reason,
            )
        )
    return grouped


def _summary(
    profile: PersonProfile,
    journeys: list[JourneyEnrollment],
    qualifications: list[QualificationResponse],
) -> ParticipantSummaryResponse:
    user: User = profile.user
    return ParticipantSummaryResponse(
        user_id=profile.user_id,
        public_id=user.public_id,
        full_name=profile.full_name,
        city=profile.city,
        state=profile.state,
        cadastral_status=profile.cadastral_status,
        profile_completed=profile.profile_completed,
        has_avatar=bool(profile.avatar_data),
        avatar_url=_avatar_url(profile),
        journeys=[JourneyResponse.model_validate(item) for item in journeys],
        qualifications=qualifications,
        created_at=profile.created_at,
    )


async def list_participants(
    db: AsyncSession,
    context: UserContext,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[ParticipantSummaryResponse]:
    profiles = list(
        (
            await db.execute(
                _scope_query(context)
                .order_by(PersonProfile.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    if not profiles:
        return []
    user_ids = [profile.user_id for profile in profiles]
    journeys = await _bulk_journeys(db, user_ids)
    qualifications = await _bulk_qualifications(db, user_ids)
    return [
        _summary(
            profile,
            journeys.get(profile.user_id, []),
            qualifications.get(profile.user_id, []),
        )
        for profile in profiles
    ]


async def _authorized_profile(
    db: AsyncSession, context: UserContext, user_id: uuid.UUID
) -> PersonProfile:
    profile = (
        (
            await db.execute(
                _scope_query(context).where(PersonProfile.user_id == user_id)
            )
        )
        .scalars()
        .first()
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participante nao encontrado.",
        )
    return profile


async def _visible_organizations(
    db: AsyncSession, context: UserContext, user_id: uuid.UUID
) -> list[ParticipantLinkedOrganization]:
    query = (
        select(ParticipantClientLink)
        .options(selectinload(ParticipantClientLink.organization))
        .where(
            ParticipantClientLink.user_id == user_id,
            ParticipantClientLink.status == ParticipantClientLinkStatus.ACTIVE,
        )
        .order_by(ParticipantClientLink.created_at.asc())
    )
    if not context.is_admin:
        organization_ids = context.client_organization_ids
        if not organization_ids:
            return []
        query = query.where(
            ParticipantClientLink.organization_id.in_(organization_ids)
        )
    links = (await db.execute(query)).scalars().all()
    return [
        ParticipantLinkedOrganization(
            organization_id=link.organization_id,
            organization_name=(
                link.organization.name if link.organization else None
            ),
            purpose=link.purpose,
            status=link.status.value,
            valid_from=link.valid_from,
        )
        for link in links
    ]


async def get_participant(
    db: AsyncSession, context: UserContext, user_id: uuid.UUID
) -> ParticipantDetailResponse:
    profile = await _authorized_profile(db, context, user_id)
    journeys = (await _bulk_journeys(db, [user_id])).get(user_id, [])
    qualifications = (await _bulk_qualifications(db, [user_id])).get(user_id, [])
    organizations = await _visible_organizations(db, context, user_id)
    cpf = crypto_manager.decrypt_data(profile.cpf_encrypted)
    phone = crypto_manager.decrypt_data(profile.phone_encrypted)
    summary = _summary(profile, journeys, qualifications)
    return ParticipantDetailResponse(
        **summary.model_dump(),
        social_name=profile.social_name,
        cpf_masked=mask_cpf(cpf),
        phone_masked=mask_phone(phone),
        birth_date=profile.birth_date,
        gender=profile.gender,
        organizations=organizations,
    )


async def participant_avatar(
    db: AsyncSession, context: UserContext, user_id: uuid.UUID
) -> PersonProfile:
    return await _authorized_profile(db, context, user_id)


def _validation_response(
    event: ParticipantValidationEvent, reviewer: Optional[User]
) -> ParticipantValidationResponse:
    return ParticipantValidationResponse(
        id=event.id,
        user_id=event.user_id,
        scope=event.scope,
        status=event.status,
        reviewer_user_id=event.reviewer_user_id,
        reviewer_public_id=reviewer.public_id if reviewer else None,
        organization_id=event.organization_id,
        notes=event.notes,
        created_at=event.created_at,
    )


async def create_validation_event(
    db: AsyncSession,
    reviewer: User,
    user_id: uuid.UUID,
    payload: ParticipantValidationCreate,
    request: Optional[Request] = None,
) -> ParticipantValidationResponse:
    profile = (
        (await db.execute(select(PersonProfile).where(PersonProfile.user_id == user_id)))
        .scalars()
        .first()
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participante nao encontrado.",
        )
    event = ParticipantValidationEvent(
        user_id=user_id,
        scope=payload.scope,
        status=payload.status,
        reviewer_user_id=reviewer.id,
        organization_id=payload.organization_id,
        notes=payload.notes,
    )
    db.add(event)
    if payload.scope in {
        ParticipantValidationScope.GLOBAL,
        ParticipantValidationScope.PROFILE,
    }:
        profile.cadastral_status = payload.status
        profile.cadastral_status_updated_at = _now()
    audit_service.record(
        db,
        action="participant.validation_recorded",
        entity_type="ParticipantValidationEvent",
        actor=reviewer,
        entity_id=str(event.id),
        organization_id=payload.organization_id,
        details={
            "user_id": str(user_id),
            "scope": payload.scope.value,
            "status": payload.status.value,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(event)
    return _validation_response(event, reviewer)


async def list_validation_events(
    db: AsyncSession, user_id: uuid.UUID
) -> list[ParticipantValidationResponse]:
    rows = (
        await db.execute(
            select(ParticipantValidationEvent)
            .options(selectinload(ParticipantValidationEvent.reviewer))
            .where(ParticipantValidationEvent.user_id == user_id)
            .order_by(ParticipantValidationEvent.created_at.desc())
        )
    ).scalars().all()
    return [
        _validation_response(event, event.reviewer)
        for event in rows
    ]
