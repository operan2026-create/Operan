import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_context, get_db, require_admin, UserContext
from app.schemas.participant import (
    ParticipantDetailResponse,
    ParticipantSummaryResponse,
    ParticipantValidationCreate,
    ParticipantValidationResponse,
)
from app.services import account_service, participant_directory_service

router = APIRouter(prefix="/participants", tags=["Participants"])


def _require_viewer(context: UserContext) -> None:
    if not context.is_admin and not context.is_client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administracao e contratantes autorizados.",
        )


@router.get("", response_model=List[ParticipantSummaryResponse])
async def list_participants(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    _require_viewer(context)
    return await participant_directory_service.list_participants(
        db, context, limit=limit, offset=offset
    )


@router.get("/{user_id}", response_model=ParticipantDetailResponse)
async def get_participant(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    _require_viewer(context)
    return await participant_directory_service.get_participant(db, context, user_id)


@router.get("/{user_id}/avatar")
async def get_participant_avatar(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    _require_viewer(context)
    profile = await participant_directory_service.participant_avatar(
        db, context, user_id
    )
    content = account_service.avatar_bytes(profile)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foto de perfil nao encontrada.",
        )
    return Response(
        content=content,
        media_type=profile.avatar_mime_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get(
    "/{user_id}/validations",
    response_model=List[ParticipantValidationResponse],
)
async def list_participant_validations(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    return await participant_directory_service.list_validation_events(db, user_id)


@router.post(
    "/{user_id}/validations",
    response_model=ParticipantValidationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_participant_validation(
    user_id: uuid.UUID,
    payload: ParticipantValidationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    return await participant_directory_service.create_validation_event(
        db, context.user, user_id, payload, request
    )
