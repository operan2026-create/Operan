from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.core.deps import (
    get_db,
    get_current_user_context,
    require_admin,
    require_professional,
    UserContext,
)
from app.models.mission import MissionStatus
from app.models.network import Professional
from app.models.user import UserStatus
from app.services import mission_service, network_service
from app.schemas.mission import MissionCreate, MissionResponse
from app.schemas.participant import (
    MissionApplicationDecision,
    MissionApplicationResponse,
    MissionInvitationCreate,
    MissionInvitationResponse,
)

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
    participant_user = None

    if context.is_admin:
        if only_my:
            assigned_user = context.user.id
    elif context.is_client:
        org_ids = context.client_organization_ids
    elif context.is_participant:
        # Nunca expor missões de terceiros: apenas as próprias ou abertas.
        participant_user = context.user.id
        if only_my:
            assigned_user = context.user.id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: usuário sem perfil operacional.",
        )

    missions = await mission_service.list_missions(
        db,
        status=status,
        city=city,
        state=state,
        assigned_user_id=assigned_user,
        organization_ids=org_ids,
        participant_user_id=participant_user,
    )
    return [MissionResponse.model_validate(m) for m in missions]


@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
async def create_mission(
    mission_in: MissionCreate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Administradores ou gestores de organização cliente podem criar missões.",
        )

    location = None
    if mission_in.location_id:
        location = await network_service.get_location(db, mission_in.location_id)
        if not location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Local de aplicação informado não existe.",
            )

    if context.is_admin:
        # Admin keeps explicit status/assignment, but references are validated.
        if mission_in.assigned_user_id:
            target = await db.execute(
                select(Professional).where(
                    Professional.user_id == mission_in.assigned_user_id
                )
            )
            if not target.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="O usuário atribuído não possui perfil de participante.",
                )
        if mission_in.status == MissionStatus.ASSIGNED and not mission_in.assigned_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missão ASSIGNED exige um participante atribuído.",
            )
    else:
        # Client managers may only operate inside their own organization.
        if not location or not location.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missões de cliente exigem um local vinculado à sua organização.",
            )
        if not context.is_manager_of(location.organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado ao local de outra organização.",
            )

        if mission_in.assigned_user_id:
            target = await db.execute(
                select(Professional)
                .join(Professional.user)
                .where(
                    Professional.user_id == mission_in.assigned_user_id,
                    Professional.user.has(status=UserStatus.ACTIVE),
                )
            )
            if not target.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="O participante atribuído não está ativo na rede.",
                )
            mission_in.status = MissionStatus.ASSIGNED
        else:
            mission_in.status = MissionStatus.OPEN

        # Derived from the verified location, never from client input.
        mission_in.city = location.city
        mission_in.state = location.state

    mission = await mission_service.create_mission(db, mission_in)
    return MissionResponse.model_validate(mission)


@router.post(
    "/{mission_id}/applications",
    response_model=MissionApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_mission(
    mission_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_professional),
):
    application = await mission_service.apply_to_mission(
        db, context.user, mission_id, request
    )
    return mission_service._application_response(
        application, context.user, context.person_profile
    )


@router.get("/applications/me", response_model=List[MissionApplicationResponse])
async def list_my_applications(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    return await mission_service.list_applications(db, context)


@router.post(
    "/{mission_id}/invitations",
    response_model=List[MissionInvitationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def invite_professionals(
    mission_id: UUID,
    payload: MissionInvitationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    return await mission_service.invite_professionals(
        db, context, mission_id, payload, request
    )


@router.get(
    "/{mission_id}/invitations", response_model=List[MissionInvitationResponse]
)
async def list_mission_invitations(
    mission_id: UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    return await mission_service.list_mission_invitations(db, context, mission_id)


@router.get("/invitations/me", response_model=List[MissionInvitationResponse])
async def list_my_mission_invitations(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_professional),
):
    return await mission_service.list_my_mission_invitations(db, context.user)


@router.post(
    "/invitations/{invitation_id}/accept",
    response_model=MissionInvitationResponse,
)
async def accept_mission_invitation(
    invitation_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_professional),
):
    return await mission_service.respond_mission_invitation(
        db, context.user, invitation_id, True, request
    )


@router.post(
    "/invitations/{invitation_id}/decline",
    response_model=MissionInvitationResponse,
)
async def decline_mission_invitation(
    invitation_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_professional),
):
    return await mission_service.respond_mission_invitation(
        db, context.user, invitation_id, False, request
    )


@router.get(
    "/{mission_id}/applications", response_model=List[MissionApplicationResponse]
)
async def list_mission_applications(
    mission_id: UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    return await mission_service.list_applications(db, context, mission_id)


@router.patch(
    "/applications/{application_id}/decision",
    response_model=MissionApplicationResponse,
)
async def decide_mission_application(
    application_id: UUID,
    payload: MissionApplicationDecision,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    return await mission_service.decide_application(
        db, context, application_id, payload, request
    )


@router.delete(
    "/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def withdraw_mission_application(
    application_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    await mission_service.withdraw_application(
        db, context.user, application_id, request
    )


@router.patch("/{mission_id}/status", response_model=MissionResponse)
async def update_status(
    mission_id: UUID,
    body: MissionStatusUpdate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    mission = await mission_service.get_mission(db, mission_id)
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Missão não encontrada.")

    if not mission_service.validate_transition(mission.status, body.status):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transição inválida de {mission.status.value} para {body.status.value}.",
        )

    if context.is_admin:
        pass
    elif context.is_client_manager:
        organization_id = mission.location.organization_id if mission.location else None
        if not organization_id or not context.is_manager_of(organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado a missão de outra organização.",
            )
        if body.status not in mission_service.CLIENT_MANAGER_TARGET_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestores clientes não podem aprovar a execução da missão.",
            )
    elif context.is_participant:
        if mission.assigned_user_id != context.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: a missão não está atribuída a você.",
            )
        if body.status not in mission_service.PARTICIPANT_TARGET_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Participantes só podem iniciar ou concluir as próprias missões.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: usuário sem perfil operacional.",
        )

    if body.status == MissionStatus.ASSIGNED and not mission.assigned_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível atribuir uma missão sem participante.",
        )

    mission = await mission_service.update_mission_status(db, mission, body.status)
    return MissionResponse.model_validate(mission)


@router.post("/seed", status_code=status.HTTP_200_OK)
async def seed_missions(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    await mission_service.seed_default_missions(db)
    return {"status": "ok", "message": "Missões territoriais semeadas com sucesso."}
