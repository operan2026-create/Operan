from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.mission import Mission, MissionType, MissionStatus
from app.models.network import Location
from app.schemas.mission import MissionCreate

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
    if organization_ids is not None:
        query = query.join(Location, Mission.location_id == Location.id).where(Location.organization_id.in_(organization_ids))

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
            "created_at": m.created_at,
            "location_name": m.location.name if m.location else None,
        })
    return output

async def update_mission_status(
    db: AsyncSession,
    mission_id: UUID,
    status: MissionStatus,
) -> Optional[Mission]:
    res = await db.execute(select(Mission).where(Mission.id == mission_id))
    m = res.scalars().first()
    if not m:
        return None
    m.status = status
    await db.commit()
    await db.refresh(m)
    return m

async def seed_default_missions(db: AsyncSession):
    res = await db.execute(select(Mission))
    if res.scalars().first():
        return

    # Fetch seeded locations
    loc_res = await db.execute(select(Location))
    locations = loc_res.scalars().all()
    loc1 = locations[0] if len(locations) > 0 else None
    loc2 = locations[1] if len(locations) > 1 else None
    loc3 = locations[2] if len(locations) > 2 else None

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
