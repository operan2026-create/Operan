from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.mission import Mission, MissionType, MissionStatus
from app.models.participant import (
    ApplicationStatus,
    JourneyEnrollment,
    JourneyStatus,
    JourneyType,
    MissionApplication,
    MissionInvitation,
    MissionInvitationStatus,
    PersonProfile,
)
from app.models.user import User, UserStatus
from app.schemas.participant import (
    MissionApplicationDecision,
    MissionApplicationResponse,
    MissionInvitationCreate,
    MissionInvitationResponse,
)
from app.services import account_service, audit_service, qualification_service
from app.models.network import Location
from app.schemas.mission import MissionCreate

# Explicit mission state machine. Terminal states have no outgoing transitions.
MISSION_TRANSITIONS = {
    MissionStatus.OPEN: {MissionStatus.ASSIGNED, MissionStatus.CANCELLED},
    MissionStatus.ASSIGNED: {MissionStatus.IN_PROGRESS, MissionStatus.CANCELLED},
    MissionStatus.IN_PROGRESS: {MissionStatus.COMPLETED, MissionStatus.CANCELLED},
    MissionStatus.COMPLETED: set(),
    MissionStatus.CANCELLED: set(),
}

# Statuses a client manager may apply. Clients never approve completion.
CLIENT_MANAGER_TARGET_STATUSES = {MissionStatus.ASSIGNED, MissionStatus.CANCELLED}
# Statuses a participant may apply to a mission assigned to them.
PARTICIPANT_TARGET_STATUSES = {MissionStatus.IN_PROGRESS, MissionStatus.COMPLETED}


async def create_mission(db: AsyncSession, mission_in: MissionCreate) -> Mission:
    mission = Mission(
        title=mission_in.title,
        mission_type=mission_in.mission_type,
        status=mission_in.status,
        location_id=mission_in.location_id,
        assigned_user_id=mission_in.assigned_user_id,
        city=mission_in.city,
        state=mission_in.state.upper(),
        reward_amount=mission_in.reward_amount,
        deadline=mission_in.deadline,
        checklist=mission_in.checklist,
        required_function=(mission_in.required_function.upper() if mission_in.required_function else None),
    )
    db.add(mission)
    await db.commit()
    await db.refresh(mission)
    return mission


async def list_missions(
    db: AsyncSession,
    status: Optional[MissionStatus] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    assigned_user_id: Optional[UUID] = None,
    organization_ids: Optional[List[UUID]] = None,
    participant_user_id: Optional[UUID] = None,
) -> List[dict]:
    query = (
        select(Mission)
        .options(selectinload(Mission.location))
        .order_by(Mission.created_at.desc())
    )
    if status:
        query = query.where(Mission.status == status)
    if city:
        query = query.where(Mission.city.ilike(f"%{city}%"))
    if state:
        query = query.where(Mission.state == state.upper())
    if assigned_user_id:
        query = query.where(Mission.assigned_user_id == assigned_user_id)
    if participant_user_id:
        # Participants only see missions assigned to them or still open.
        query = query.where(
            or_(
                Mission.assigned_user_id == participant_user_id,
                Mission.status == MissionStatus.OPEN,
            )
        )
    if organization_ids is not None:
        query = query.join(Location, Mission.location_id == Location.id).where(
            Location.organization_id.in_(organization_ids)
        )

    res = await db.execute(query)

    missions = res.scalars().all()
    output = []
    for m in missions:
        output.append({
            "id": m.id,
            "title": m.title,
            "mission_type": m.mission_type,
            "status": m.status,
            "location_id": m.location_id,
            "assigned_user_id": m.assigned_user_id,
            "city": m.city,
            "state": m.state,
            "reward_amount": float(m.reward_amount) if m.reward_amount else 0.0,
            "deadline": m.deadline,
            "checklist": m.checklist,
            "required_function": m.required_function,
            "created_at": m.created_at,
            "location_name": m.location.name if m.location else None,
        })
    return output


async def get_mission(db: AsyncSession, mission_id: UUID) -> Optional[Mission]:
    res = await db.execute(
        select(Mission)
        .where(Mission.id == mission_id)
        .options(selectinload(Mission.location))
    )
    return res.scalars().first()


async def _lock_mission(db: AsyncSession, mission_id: UUID) -> Optional[Mission]:
    """Loads a mission with a row lock so assignment decisions are atomic.

    PostgreSQL honors ``FOR UPDATE`` (SQLite ignores it, but serializes writes).
    Callers must re-check the state after locking before writing.
    """
    res = await db.execute(
        select(Mission)
        .where(Mission.id == mission_id)
        .options(selectinload(Mission.location))
        .with_for_update()
    )
    return res.scalars().first()


async def _lock_mission_invitation(
    db: AsyncSession, invitation_id: UUID
) -> Optional[MissionInvitation]:
    res = await db.execute(
        select(MissionInvitation)
        .where(MissionInvitation.id == invitation_id)
        .with_for_update()
    )
    return res.scalars().first()


def validate_transition(current: MissionStatus, target: MissionStatus) -> bool:
    return target in MISSION_TRANSITIONS.get(current, set())


async def update_mission_status(
    db: AsyncSession,
    mission: Mission,
    status: MissionStatus,
) -> Mission:
    mission.status = status
    await db.commit()
    await db.refresh(mission)
    return mission


async def seed_default_missions(db: AsyncSession):
    res = await db.execute(select(Mission))
    if res.scalars().first():
        return

    # Fetch seeded locations
    loc_res = await db.execute(select(Location))
    locations = loc_res.scalars().all()
    loc1 = locations[0] if len(locations) > 0 else None
    loc2 = locations[1] if len(locations) > 1 else None

    m1 = Mission(
        title="Vistoria Técnica de Infraestrutura e Acessibilidade",
        mission_type=MissionType.VISTORIA,
        status=MissionStatus.OPEN,
        location_id=loc2.id if loc2 else None,
        city="Brasília",
        state="DF",
        reward_amount=180.00,
        checklist=[
            {"item": "Verificar rampa de acesso e elevador", "done": False},
            {"item": "Fotografar quadro de energia e salas", "done": False},
            {"item": "Testar funcionamento de ar-condicionado em 100% das salas", "done": False},
            {"item": "Conferir capacidade de carteiras por sala", "done": False},
        ]
    )

    m2 = Mission(
        title="Reconfirmação Pré-Operação (Concurso Nacional)",
        mission_type=MissionType.CONFIRMACAO,
        status=MissionStatus.IN_PROGRESS,
        location_id=loc1.id if loc1 else None,
        city="Salvador",
        state="BA",
        reward_amount=150.00,
        checklist=[
            {"item": "Reunião com diretor da unidade", "done": True},
            {"item": "Checagem de portões e rotas de segurança", "done": True},
            {"item": "Confirmação de liberação do prédio no fim de semana", "done": False},
        ]
    )

    m3 = Mission(
        title="Captação Territorial de Novos Prédios Escolares",
        mission_type=MissionType.CAPTACAO,
        status=MissionStatus.OPEN,
        city="Rio de Janeiro",
        state="RJ",
        reward_amount=250.00,
        checklist=[
            {"item": "Identificar escola com capacidade superior a 400 carteiras", "done": False},
            {"item": "Coletar contato do responsável pedagógico/administrativo", "done": False},
            {"item": "Preencher pré-cadastro do local no sistema OPERAN", "done": False},
        ]
    )

    db.add_all([m1, m2, m3])
    await db.commit()


async def apply_to_mission(
    db: AsyncSession,
    user: User,
    mission_id: UUID,
    request=None,
) -> MissionApplication:
    mission = await get_mission(db, mission_id)
    if not mission:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Missao nao encontrada.")
    if mission.status != MissionStatus.OPEN:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Apenas missoes abertas recebem inscricoes.",
        )
    journey = (
        (
            await db.execute(
                select(JourneyEnrollment).where(
                    JourneyEnrollment.user_id == user.id,
                    JourneyEnrollment.journey_type == JourneyType.PROFESSIONALS,
                    JourneyEnrollment.status == JourneyStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .first()
    )
    if not journey:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Jornada profissional ativa obrigatoria para se inscrever.",
        )
    if mission.required_function and not await qualification_service.has_valid_qualification(
        db, user.id, mission.required_function
    ):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Qualificacao ativa obrigatoria para a funcao {mission.required_function}.",
        )
    existing = (
        (
            await db.execute(
                select(MissionApplication).where(
                    MissionApplication.mission_id == mission_id,
                    MissionApplication.user_id == user.id,
                )
            )
        )
        .scalars()
        .first()
    )
    if existing:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Voce ja possui inscricao nesta missao.",
        )
    application = MissionApplication(
        mission_id=mission_id,
        user_id=user.id,
        status=ApplicationStatus.APPLIED,
    )
    db.add(application)
    await db.flush()
    audit_service.record(
        db,
        action="mission.application_created",
        entity_type="MissionApplication",
        actor=user,
        entity_id=str(application.id),
        details={"mission_id": str(mission_id)},
        request=request,
    )
    await db.commit()
    await db.refresh(application)
    return application


async def withdraw_application(
    db: AsyncSession,
    user: User,
    application_id: UUID,
    request=None,
) -> MissionApplication:
    from fastapi import HTTPException, status

    application = (
        (await db.execute(select(MissionApplication).where(MissionApplication.id == application_id)))
        .scalars()
        .first()
    )
    if not application or application.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inscricao nao encontrada."
        )
    if application.status != ApplicationStatus.APPLIED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somente inscricoes pendentes podem ser retiradas.",
        )
    application.status = ApplicationStatus.WITHDRAWN
    audit_service.record(
        db,
        action="mission.application_withdrawn",
        entity_type="MissionApplication",
        actor=user,
        entity_id=str(application.id),
        request=request,
    )
    await db.commit()
    await db.refresh(application)
    return application


def _application_response(
    application: MissionApplication,
    user: Optional[User] = None,
    profile: Optional[PersonProfile] = None,
) -> MissionApplicationResponse:
    return MissionApplicationResponse(
        id=application.id,
        mission_id=application.mission_id,
        user_id=application.user_id,
        public_id=user.public_id if user else None,
        full_name=profile.full_name if profile else None,
        status=application.status,
        applied_at=application.applied_at,
        decided_at=application.decided_at,
        notes=application.notes,
    )


async def list_applications(
    db: AsyncSession, context, mission_id: Optional[UUID] = None
) -> list[MissionApplicationResponse]:
    from fastapi import HTTPException, status

    query = select(MissionApplication)
    if mission_id:
        query = query.where(MissionApplication.mission_id == mission_id)
    if not context.is_admin:
        if context.is_client:
            if mission_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Informe a missao para listar candidatos.",
                )
            mission = await get_mission(db, mission_id)
            org_id = mission.location.organization_id if mission and mission.location else None
            if not org_id or not context.has_client_org_access(org_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
        else:
            query = query.where(MissionApplication.user_id == context.user.id)
    rows = (await db.execute(query.order_by(MissionApplication.applied_at.desc()))).scalars().all()
    output = []
    for application in rows:
        user = (await db.execute(select(User).where(User.id == application.user_id))).scalars().first()
        profile = (
            await db.execute(select(PersonProfile).where(PersonProfile.user_id == application.user_id))
        ).scalars().first()
        output.append(_application_response(application, user, profile))
    return output


async def decide_application(
    db: AsyncSession,
    context,
    application_id: UUID,
    payload: MissionApplicationDecision,
    request=None,
) -> MissionApplicationResponse:
    from fastapi import HTTPException, status

    application = (
        (await db.execute(select(MissionApplication).where(MissionApplication.id == application_id)))
        .scalars()
        .first()
    )
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inscricao nao encontrada."
        )
    # Lock the mission row before evaluating the decision. Concurrent decisions
    # therefore observe each other's committed assignment instead of both
    # reading OPEN and selecting two different professionals.
    mission = await _lock_mission(db, application.mission_id)
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Missao nao encontrada.")
    # Re-read the application under its own row lock. Without this, two
    # decisions on the same application could both see APPLIED and overwrite
    # each other after the mission lock is acquired.
    application = (
        (
            await db.execute(
                select(MissionApplication)
                .where(MissionApplication.id == application_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .first()
    )
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inscricao nao encontrada."
        )
    if not context.is_admin:
        org_id = mission.location.organization_id if mission.location else None
        if not context.is_client_manager or not org_id or not context.is_manager_of(org_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    if application.status not in {ApplicationStatus.APPLIED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somente inscricoes pendentes podem ser decididas.",
        )
    if payload.status not in {ApplicationStatus.SELECTED, ApplicationStatus.REJECTED}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Decisao deve ser SELECTED ou REJECTED.",
        )
    if payload.status == ApplicationStatus.SELECTED:
        if mission.status != MissionStatus.OPEN or mission.assigned_user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A missao nao esta aberta para selecao.",
            )
        mission.assigned_user_id = application.user_id
        mission.status = MissionStatus.ASSIGNED
        pending_invites = (
            await db.execute(
                select(MissionInvitation).where(
                    MissionInvitation.mission_id == mission.id,
                    MissionInvitation.status == MissionInvitationStatus.INVITED,
                )
            )
        ).scalars().all()
        for invite in pending_invites:
            invite.status = MissionInvitationStatus.CANCELLED
            invite.responded_at = datetime.now(timezone.utc)
    application.status = payload.status
    application.notes = payload.notes
    application.decided_at = datetime.now(timezone.utc)
    application.decided_by_user_id = context.user.id
    audit_service.record(
        db,
        action="mission.application_decided",
        entity_type="MissionApplication",
        actor=context.user,
        entity_id=str(application.id),
        details={"status": payload.status.value, "mission_id": str(mission.id)},
        request=request,
    )
    await db.commit()
    await db.refresh(application)
    user = (await db.execute(select(User).where(User.id == application.user_id))).scalars().first()
    profile = (
        await db.execute(select(PersonProfile).where(PersonProfile.user_id == application.user_id))
    ).scalars().first()
    return _application_response(application, user, profile)


def _invitation_response(
    invitation: MissionInvitation,
    mission: Optional[Mission] = None,
    user: Optional[User] = None,
    profile: Optional[PersonProfile] = None,
) -> MissionInvitationResponse:
    location = mission.location if mission else None
    return MissionInvitationResponse(
        id=invitation.id,
        mission_id=invitation.mission_id,
        user_id=invitation.user_id,
        public_id=user.public_id if user else None,
        full_name=profile.full_name if profile else None,
        function_name=mission.required_function if mission else None,
        status=invitation.status,
        message=invitation.message,
        mission_title=mission.title if mission else None,
        mission_status=mission.status.value if mission else None,
        mission_city=mission.city if mission else None,
        mission_state=mission.state if mission else None,
        location_name=location.name if location else None,
        reward_amount=float(mission.reward_amount) if mission and mission.reward_amount else None,
        created_at=invitation.created_at,
        responded_at=invitation.responded_at,
    )


async def _require_mission_manager(db: AsyncSession, context, mission_id: UUID) -> Mission:
    from fastapi import HTTPException, status

    mission = await get_mission(db, mission_id)
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Missao nao encontrada.")
    if context.is_admin:
        return mission
    org_id = mission.location.organization_id if mission.location else None
    if not context.is_client_manager or not org_id or not context.is_manager_of(org_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    return mission


async def invite_professionals(
    db: AsyncSession,
    context,
    mission_id: UUID,
    payload: MissionInvitationCreate,
    request=None,
) -> list[MissionInvitationResponse]:
    from fastapi import HTTPException, status

    mission = await _require_mission_manager(db, context, mission_id)
    if mission.status != MissionStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somente missoes abertas recebem convites diretos.",
        )

    created: list[MissionInvitation] = []
    seen: set[UUID] = set()
    for user_id in payload.user_ids:
        if user_id in seen:
            continue
        seen.add(user_id)
        user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
        if not user or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profissional nao encontrado ou inativo.",
            )
        journey = (
            (
                await db.execute(
                    select(JourneyEnrollment).where(
                        JourneyEnrollment.user_id == user_id,
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
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O profissional precisa ter jornada profissional ativa.",
            )
        if mission.required_function and not await qualification_service.has_valid_qualification(
            db, user_id, mission.required_function
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"O profissional nao possui qualificacao ativa para {mission.required_function}.",
            )
        existing_application = (
            (
                await db.execute(
                    select(MissionApplication).where(
                        MissionApplication.mission_id == mission_id,
                        MissionApplication.user_id == user_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing_application:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O profissional ja possui inscricao nesta missao.",
            )
        existing_invite = (
            (
                await db.execute(
                    select(MissionInvitation).where(
                        MissionInvitation.mission_id == mission_id,
                        MissionInvitation.user_id == user_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing_invite:
            if existing_invite.status != MissionInvitationStatus.INVITED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="O profissional ja respondeu a um convite para esta missao.",
                )
            existing_invite.message = payload.message
            created.append(existing_invite)
            continue
        invitation = MissionInvitation(
            mission_id=mission_id,
            user_id=user_id,
            invited_by_user_id=context.user.id,
            status=MissionInvitationStatus.INVITED,
            message=payload.message,
        )
        db.add(invitation)
        created.append(invitation)

    await db.flush()
    for invitation in created:
        audit_service.record(
            db,
            action="mission.invitation_created",
            entity_type="MissionInvitation",
            actor=context.user,
            entity_id=str(invitation.id),
            details={"mission_id": str(mission_id), "user_id": str(invitation.user_id)},
            request=request,
        )
    await db.commit()

    output = []
    for invitation in created:
        user = (await db.execute(select(User).where(User.id == invitation.user_id))).scalars().first()
        profile = (
            await db.execute(select(PersonProfile).where(PersonProfile.user_id == invitation.user_id))
        ).scalars().first()
        output.append(_invitation_response(invitation, mission, user, profile))
    return output


async def list_mission_invitations(
    db: AsyncSession, context, mission_id: UUID
) -> list[MissionInvitationResponse]:
    mission = await _require_mission_manager(db, context, mission_id)
    rows = (
        await db.execute(
            select(MissionInvitation)
            .where(MissionInvitation.mission_id == mission_id)
            .order_by(MissionInvitation.created_at.desc())
        )
    ).scalars().all()
    output = []
    for invitation in rows:
        user = (await db.execute(select(User).where(User.id == invitation.user_id))).scalars().first()
        profile = (
            await db.execute(select(PersonProfile).where(PersonProfile.user_id == invitation.user_id))
        ).scalars().first()
        output.append(_invitation_response(invitation, mission, user, profile))
    return output


async def list_my_mission_invitations(
    db: AsyncSession, user: User
) -> list[MissionInvitationResponse]:
    rows = (
        await db.execute(
            select(MissionInvitation)
            .where(MissionInvitation.user_id == user.id)
            .order_by(MissionInvitation.created_at.desc())
        )
    ).scalars().all()
    output = []
    for invitation in rows:
        mission = await get_mission(db, invitation.mission_id)
        profile = (
            await db.execute(select(PersonProfile).where(PersonProfile.user_id == user.id))
        ).scalars().first()
        output.append(_invitation_response(invitation, mission, user, profile))
    return output


async def respond_mission_invitation(
    db: AsyncSession,
    user: User,
    invitation_id: UUID,
    accept: bool,
    request=None,
) -> MissionInvitationResponse:
    from fastapi import HTTPException, status

    invitation = (
        (await db.execute(select(MissionInvitation).where(MissionInvitation.id == invitation_id)))
        .scalars()
        .first()
    )
    if not invitation or invitation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Convite nao encontrado."
        )
    # Lock the mission first, then the invitation, so concurrent acceptances
    # serialize on the mission and only one can occupy the open slot.
    mission = await _lock_mission(db, invitation.mission_id)
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Missao nao encontrada.")
    invitation = await _lock_mission_invitation(db, invitation_id)
    if not invitation or invitation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Convite nao encontrado."
        )
    if invitation.status != MissionInvitationStatus.INVITED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este convite ja foi respondido ou cancelado.",
        )

    now = datetime.now(timezone.utc)
    if accept:
        if mission.status != MissionStatus.OPEN or mission.assigned_user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A missao nao esta mais disponivel.",
            )
        if mission.required_function and not await qualification_service.has_valid_qualification(
            db, user.id, mission.required_function
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Qualificacao ativa obrigatoria para aceitar esta missao.",
            )
        mission.assigned_user_id = user.id
        mission.status = MissionStatus.ASSIGNED
        invitation.status = MissionInvitationStatus.ACCEPTED
        organization_id = mission.organization_id or (
            mission.location.organization_id if mission.location else None
        )
        if organization_id:
            await account_service.ensure_participant_client_link(
                db,
                user=user,
                organization_id=organization_id,
                purpose="MISSION_PARTICIPANT",
                source_mission_id=mission.id,
                created_by_user_id=invitation.invited_by_user_id,
            )
        other_invites = (
            await db.execute(
                select(MissionInvitation).where(
                    MissionInvitation.mission_id == mission.id,
                    MissionInvitation.id != invitation.id,
                    MissionInvitation.status == MissionInvitationStatus.INVITED,
                )
            )
        ).scalars().all()
        for other in other_invites:
            other.status = MissionInvitationStatus.CANCELLED
            other.responded_at = now
    else:
        invitation.status = MissionInvitationStatus.DECLINED
    invitation.responded_at = now
    audit_service.record(
        db,
        action="mission.invitation_responded",
        entity_type="MissionInvitation",
        actor=user,
        entity_id=str(invitation.id),
        details={
            "mission_id": str(invitation.mission_id),
            "accepted": accept,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(invitation)
    profile = (
        await db.execute(select(PersonProfile).where(PersonProfile.user_id == user.id))
    ).scalars().first()
    return _invitation_response(invitation, mission, user, profile)
