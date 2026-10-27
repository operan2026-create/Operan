import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.network import Location, LocationStatus
from app.models.participant import (
    LocationWorkflowEvent,
    RepresentativeLinkStatus,
    RepresentativeSchoolLink,
    WorkflowStage,
    WorkflowStatus,
)
from app.models.user import User
from app.schemas.participant import (
    RepresentativeLinkResponse,
    RepresentativeLinkUpdate,
    WorkflowDecisionRequest,
    WorkflowEventResponse,
)
from app.services import audit_service

STAGE_ORDER = [
    WorkflowStage.CAPTURE,
    WorkflowStage.DOCUMENTATION,
    WorkflowStage.INSPECTION,
    WorkflowStage.RELEASE,
]
REPRESENTATIVE_STAGES = {
    WorkflowStage.CAPTURE,
    WorkflowStage.DOCUMENTATION,
    WorkflowStage.INSPECTION,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _link_response(link: RepresentativeSchoolLink) -> RepresentativeLinkResponse:
    return RepresentativeLinkResponse(
        id=link.id,
        location_id=link.location_id,
        location_name=link.location.name if link.location else None,
        city=link.location.city if link.location else None,
        state=link.location.state if link.location else None,
        status=link.status,
        responsibilities=link.responsibilities,
        started_at=link.started_at,
    )


async def list_links_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> list[RepresentativeSchoolLink]:
    result = await db.execute(
        select(RepresentativeSchoolLink)
        .options(selectinload(RepresentativeSchoolLink.location))
        .where(
            RepresentativeSchoolLink.representative_user_id == user_id,
            RepresentativeSchoolLink.status == RepresentativeLinkStatus.ACTIVE,
        )
        .order_by(RepresentativeSchoolLink.started_at.desc())
    )
    return list(result.scalars().all())


async def list_schools_for_representative(
    db: AsyncSession, user_id: uuid.UUID
) -> list[RepresentativeLinkResponse]:
    return [_link_response(link) for link in await list_links_for_user(db, user_id)]


async def get_link_for_user(
    db: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID
) -> RepresentativeSchoolLink:
    link = (
        (
            await db.execute(
                select(RepresentativeSchoolLink)
                .options(selectinload(RepresentativeSchoolLink.location))
                .where(
                    RepresentativeSchoolLink.representative_user_id == user_id,
                    RepresentativeSchoolLink.location_id == location_id,
                    RepresentativeSchoolLink.status == RepresentativeLinkStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voce nao possui vinculo ativo com esta escola.",
        )
    return link


async def list_representatives_for_school(
    db: AsyncSession, context, location_id: uuid.UUID
) -> list[RepresentativeLinkResponse]:
    location = (
        (await db.execute(select(Location).where(Location.id == location_id))).scalars().first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escola nao encontrada.")
    if not context.is_admin and (
        not location.organization_id or not context.has_client_org_access(location.organization_id)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    links = (
        await db.execute(
            select(RepresentativeSchoolLink)
            .options(selectinload(RepresentativeSchoolLink.location))
            .where(RepresentativeSchoolLink.location_id == location_id)
            .order_by(RepresentativeSchoolLink.started_at.desc())
        )
    ).scalars().all()
    return [_link_response(link) for link in links]


async def update_link(
    db: AsyncSession,
    context,
    link_id: uuid.UUID,
    payload: RepresentativeLinkUpdate,
    request: Optional[Request] = None,
) -> RepresentativeLinkResponse:
    link = (
        (
            await db.execute(
                select(RepresentativeSchoolLink)
                .options(selectinload(RepresentativeSchoolLink.location))
                .where(RepresentativeSchoolLink.id == link_id)
            )
        )
        .scalars()
        .first()
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vinculo nao encontrado.")
    location = link.location
    if not context.is_admin and (
        not location or not location.organization_id or not context.is_manager_of(location.organization_id)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    link.status = payload.status
    if payload.responsibilities is not None:
        link.responsibilities = payload.responsibilities
    if payload.status in {RepresentativeLinkStatus.ENDED, RepresentativeLinkStatus.SUSPENDED}:
        link.ended_at = _now()
    audit_service.record(
        db,
        action="representative_link.updated",
        entity_type="RepresentativeSchoolLink",
        actor=context.user,
        entity_id=str(link.id),
        organization_id=location.organization_id if location else None,
        details={"status": payload.status.value},
        request=request,
    )
    await db.commit()
    await db.refresh(link)
    return _link_response(link)


async def list_workflow_events(
    db: AsyncSession, context, location_id: uuid.UUID
) -> list[WorkflowEventResponse]:
    location = (
        (await db.execute(select(Location).where(Location.id == location_id))).scalars().first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escola nao encontrada.")
    allowed = context.is_admin or (
        location.organization_id is not None
        and context.has_client_org_access(location.organization_id)
    )
    if not allowed:
        await get_link_for_user(db, context.user.id, location_id)
    events = (
        await db.execute(
            select(LocationWorkflowEvent)
            .where(LocationWorkflowEvent.location_id == location_id)
            .order_by(LocationWorkflowEvent.created_at.asc())
        )
    ).scalars().all()
    return [WorkflowEventResponse.model_validate(event) for event in events]


async def _latest_event(
    db: AsyncSession, location_id: uuid.UUID, stage: WorkflowStage
) -> Optional[LocationWorkflowEvent]:
    return (
        (
            await db.execute(
                select(LocationWorkflowEvent)
                .where(
                    LocationWorkflowEvent.location_id == location_id,
                    LocationWorkflowEvent.stage == stage,
                )
                .order_by(LocationWorkflowEvent.created_at.desc())
            )
        )
        .scalars()
        .first()
    )


async def submit_stage(
    db: AsyncSession,
    user: User,
    location_id: uuid.UUID,
    stage: WorkflowStage,
    request: Optional[Request] = None,
) -> WorkflowEventResponse:
    if stage not in REPRESENTATIVE_STAGES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Representantes nao podem solicitar a liberacao final da escola.",
        )
    link = await get_link_for_user(db, user.id, location_id)
    latest = await _latest_event(db, location_id, stage)
    if latest and latest.status == WorkflowStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta etapa ja possui uma submissao pendente de analise.",
        )
    if latest and latest.status == WorkflowStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Esta etapa ja foi aprovada."
        )
    event = LocationWorkflowEvent(
        location_id=location_id,
        stage=stage,
        status=WorkflowStatus.SUBMITTED,
        actor_user_id=user.id,
    )
    db.add(event)
    await db.flush()
    audit_service.record(
        db,
        action="location.stage_submitted",
        entity_type="Location",
        actor=user,
        entity_id=str(location_id),
        organization_id=link.location.organization_id if link.location else None,
        details={"stage": stage.value},
        request=request,
    )
    await db.commit()
    await db.refresh(event)
    return WorkflowEventResponse.model_validate(event)


async def decide_stage(
    db: AsyncSession,
    context,
    location_id: uuid.UUID,
    stage: WorkflowStage,
    payload: WorkflowDecisionRequest,
    request: Optional[Request] = None,
) -> WorkflowEventResponse:
    location = (
        (await db.execute(select(Location).where(Location.id == location_id))).scalars().first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escola nao encontrada.")
    if not context.is_admin and (
        not location.organization_id or not context.is_manager_of(location.organization_id)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")

    latest = await _latest_event(db, location_id, stage)
    if not latest or latest.status != WorkflowStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nao existe submissao pendente para esta etapa.",
        )

    stage_index = STAGE_ORDER.index(stage)
    if payload.approve and stage_index > 0:
        for previous in STAGE_ORDER[:stage_index]:
            event = await _latest_event(db, location_id, previous)
            if not event or event.status != WorkflowStatus.APPROVED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A etapa {previous.value} precisa ser aprovada antes de {stage.value}.",
                )

    latest.status = WorkflowStatus.APPROVED if payload.approve else WorkflowStatus.REJECTED
    latest.notes = payload.notes
    if payload.approve:
        if stage == WorkflowStage.INSPECTION:
            location.status = LocationStatus.VISTORIADO
        elif stage == WorkflowStage.RELEASE:
            location.status = LocationStatus.CONFIRMADO
    audit_service.record(
        db,
        action="location.stage_decided",
        entity_type="Location",
        actor=context.user,
        entity_id=str(location_id),
        organization_id=location.organization_id,
        details={
            "stage": stage.value,
            "approved": payload.approve,
            "notes": payload.notes,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(latest)
    return WorkflowEventResponse.model_validate(latest)

async def submit_stage_for_staff(
    db: AsyncSession,
    context,
    location_id: uuid.UUID,
    stage: WorkflowStage,
    request: Optional[Request] = None,
) -> WorkflowEventResponse:
    location = (
        (await db.execute(select(Location).where(Location.id == location_id))).scalars().first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escola nao encontrada.")
    if not context.is_admin and (
        not location.organization_id or not context.is_manager_of(location.organization_id)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    latest = await _latest_event(db, location_id, stage)
    if latest and latest.status == WorkflowStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta etapa ja possui uma submissao pendente de analise.",
        )
    if latest and latest.status == WorkflowStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Esta etapa ja foi aprovada."
        )
    event = LocationWorkflowEvent(
        location_id=location_id,
        stage=stage,
        status=WorkflowStatus.SUBMITTED,
        actor_user_id=context.user.id,
    )
    db.add(event)
    await db.flush()
    audit_service.record(
        db,
        action="location.stage_submitted",
        entity_type="Location",
        actor=context.user,
        entity_id=str(location_id),
        organization_id=location.organization_id,
        details={"stage": stage.value, "staff": True},
        request=request,
    )
    await db.commit()
    await db.refresh(event)
    return WorkflowEventResponse.model_validate(event)
