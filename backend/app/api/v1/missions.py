from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.core.deps import get_db, get_current_user_context, require_admin, UserContext
from app.models.mission import MissionStatus
from app.schemas.mission import MissionCreate, MissionResponse
from app.services import mission_service

router = APIRouter(prefix="/missions", tags=["Missions"])

class MissionStatusUpdate(BaseModel):
    status: MissionStatus

@router.get("", response_model=List[MissionResponse])
async def list_missions(
    status: Optional[MissionStatus] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    only_my: bool = False,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    assigned_user = None
    org_ids = None

    if context.is_admin:
        if only_my:
            assigned_user = context.user.id
    elif context.is_client:
        org_ids = context.client_organization_ids
    elif context.is_participant:
        # Participante vê apenas suas missões ou missões em aberto para candidatura
        if only_my:
            assigned_user = context.user.id
        elif not status:
            # Default for participant browsing: OPEN missions in their region or assigned to them
            pass

    missions = await mission_service.list_missions(
        db,
        status=status,
        city=city,
        state=state,
        assigned_user_id=assigned_user,
        organization_ids=org_ids,
    )
    return [MissionResponse.model_validate(m) for m in missions]

@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
async def create_mission(
    mission_in: MissionCreate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Administradores ou Clientes podem criar missões operacionais."
        )

    mission = await mission_service.create_mission(db, mission_in)
    return MissionResponse.model_validate(mission)

@router.patch("/{mission_id}/status", response_model=MissionResponse)
async def update_status(
    mission_id: UUID,
    body: MissionStatusUpdate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    mission = await mission_service.update_mission_status(db, mission_id, body.status)
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Missão não encontrada.")
    return MissionResponse.model_validate(mission)

@router.post("/seed", status_code=status.HTTP_200_OK)
async def seed_missions(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    await mission_service.seed_default_missions(db)
    return {"status": "ok", "message": "Missões territoriais semeadas com sucesso."}

