from app.security.blind_index import cpf_index
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.network import Location, Professional, LocationStatus
from app.models.participant import (
    JourneyEnrollment,
    JourneyStatus,
    JourneyType,
    ParticipantClientLink,
    ParticipantClientLinkStatus,
    ProfessionalQualification,
    QualificationStatus,
)
from app.models.user import User, UserStatus
from app.schemas.network import LocationCreate, ProfessionalCreate
from app.security.encryption import crypto_manager

async def create_location(db: AsyncSession, loc_in: LocationCreate) -> Location:
    loc = Location(
        name=loc_in.name,
        address=loc_in.address,
        city=loc_in.city,
        state=loc_in.state.upper(),
        neighborhood=loc_in.neighborhood,
        zip_code=loc_in.zip_code,
        latitude=loc_in.latitude,
        longitude=loc_in.longitude,
        total_rooms=loc_in.total_rooms,
        total_capacity=loc_in.total_capacity,
        has_accessibility=loc_in.has_accessibility,
        has_air_conditioning=loc_in.has_air_conditioning,
        status=loc_in.status,
        reliability_score=loc_in.reliability_score,
        organization_id=loc_in.organization_id,
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc

async def get_location(db: AsyncSession, location_id: UUID) -> Optional[Location]:
    res = await db.execute(select(Location).where(Location.id == location_id))
    return res.scalars().first()


async def list_locations(
    db: AsyncSession,
    city: Optional[str] = None,
    state: Optional[str] = None,
    status: Optional[LocationStatus] = None,
    organization_ids: Optional[List[UUID]] = None,
    public_only: bool = False,
) -> List[Location]:
    query = select(Location).order_by(Location.created_at.desc())
    if city:
        query = query.where(Location.city.ilike(f"%{city}%"))
    if state:
        query = query.where(Location.state == state.upper())
    if public_only:
        # Participantes veem apenas locais já confirmados para operação.
        query = query.where(Location.status == LocationStatus.CONFIRMADO)
    elif status:
        query = query.where(Location.status == status)
    if organization_ids is not None:
        query = query.where(Location.organization_id.in_(organization_ids))

    res = await db.execute(query)
    return list(res.scalars().all())


# Transições permitidas para validação de locais. Reversões exigem fluxo próprio.
LOCATION_TRANSITIONS = {
    LocationStatus.DECLARADO: {LocationStatus.VISTORIADO},
    LocationStatus.VISTORIADO: {LocationStatus.CONFIRMADO},
    LocationStatus.CONFIRMADO: set(),
}


async def update_location_status(
    db: AsyncSession,
    location_id: UUID,
    status: LocationStatus,
) -> Optional[Location]:
    res = await db.execute(select(Location).where(Location.id == location_id))
    loc = res.scalars().first()
    if not loc:
        return None
    loc.status = status
    await db.commit()
    await db.refresh(loc)
    return loc

async def create_professional(db: AsyncSession, prof_in: ProfessionalCreate) -> Professional:
    cpf_clean = "".join(filter(str.isdigit, prof_in.cpf))
    cpf_hash = cpf_index(cpf_clean)

    prof = Professional(
        user_id=prof_in.user_id,
        full_name=prof_in.full_name,
        cpf_hash=cpf_hash,
        cpf_encrypted=crypto_manager.encrypt_data(cpf_clean),
        phone_encrypted=crypto_manager.encrypt_data(prof_in.phone),
        city=prof_in.city,
        state=prof_in.state.upper(),
        operational_radius_km=prof_in.operational_radius_km,
        availability_status=prof_in.availability_status,
        reputation_score=prof_in.reputation_score,
    )
    db.add(prof)
    await db.commit()
    await db.refresh(prof)
    return prof

async def list_professionals(
    db: AsyncSession,
    city: Optional[str] = None,
    state: Optional[str] = None,
    organization_ids: Optional[list[UUID]] = None,
    function_name: Optional[str] = None,
) -> List[Professional]:
    active_users = select(User.id).where(User.status == UserStatus.ACTIVE)
    active_professionals = select(JourneyEnrollment.user_id).where(
        JourneyEnrollment.journey_type == JourneyType.PROFESSIONALS,
        JourneyEnrollment.status == JourneyStatus.ACTIVE,
    )
    query = (
        select(Professional)
        .options(selectinload(Professional.user))
        .where(
            Professional.user_id.in_(active_users),
            Professional.user_id.in_(active_professionals),
        )
        .order_by(Professional.reputation_score.desc())
    )
    if organization_ids is not None:
        if not organization_ids:
            return []
        linked_user_ids = select(ParticipantClientLink.user_id).where(
            ParticipantClientLink.organization_id.in_(organization_ids),
            ParticipantClientLink.status == ParticipantClientLinkStatus.ACTIVE,
        )
        query = query.where(Professional.user_id.in_(linked_user_ids))
    if function_name:
        valid_users = select(ProfessionalQualification.user_id).where(
            ProfessionalQualification.function_name == function_name.upper(),
            ProfessionalQualification.status == QualificationStatus.ACTIVE,
            or_(
                ProfessionalQualification.expires_at.is_(None),
                ProfessionalQualification.expires_at > datetime.now(timezone.utc),
            ),
        )
        query = query.where(Professional.user_id.in_(valid_users))

    res = await db.execute(query)
    rows = list(res.scalars().all())
    if city:
        normalized_city = city.strip().lower()
        rows = [row for row in rows if normalized_city in (row.city or "").lower()]
    if state:
        normalized_state = state.strip().upper()
        rows = [row for row in rows if (row.state or "").upper() == normalized_state]
    return rows


async def qualifications_for_users(
    db: AsyncSession, user_ids: list[UUID]
) -> dict[UUID, list[str]]:
    if not user_ids:
        return {}
    rows = (
        await db.execute(
            select(ProfessionalQualification).where(
                ProfessionalQualification.user_id.in_(user_ids),
                ProfessionalQualification.status == QualificationStatus.ACTIVE,
                or_(
                    ProfessionalQualification.expires_at.is_(None),
                    ProfessionalQualification.expires_at > datetime.now(timezone.utc),
                ),
            )
        )
    ).scalars().all()
    output: dict[UUID, list[str]] = {}
    for row in rows:
        output.setdefault(row.user_id, []).append(row.function_name)
    return output

async def seed_default_network(db: AsyncSession):
    res = await db.execute(select(Location))
    if res.scalars().first():
        return

    # Seed 3 realistic application centers
    loc1 = Location(
        name="Colégio Estadual Presidente Médici",
        address="Av. das Américas, 1200",
        city="Salvador",
        state="BA",
        neighborhood="Nazaré",
        zip_code="40040-000",
        latitude=-12.9714,
        longitude=-38.5014,
        total_rooms=32,
        total_capacity=1100,
        has_accessibility=True,
        has_air_conditioning=True,
        status=LocationStatus.CONFIRMADO,
        reliability_score=99.0,
    )
    loc2 = Location(
        name="Universidade Católica de Brasília (UCB) - Campus I",
        address="QS 07 Lote 01 EPCT",
        city="Brasília",
        state="DF",
        neighborhood="Taguatinga",
        zip_code="71966-700",
        latitude=-15.8667,
        longitude=-48.0289,
        total_rooms=55,
        total_capacity=2200,
        has_accessibility=True,
        has_air_conditioning=True,
        status=LocationStatus.VISTORIADO,
        reliability_score=96.5,
    )
    loc3 = Location(
        name="Escola Municipal Gonçalves Dias",
        address="Rua São Cristóvão, 450",
        city="Rio de Janeiro",
        state="RJ",
        neighborhood="São Cristóvão",
        zip_code="20921-440",
        latitude=-22.9068,
        longitude=-43.1729,
        total_rooms=18,
        total_capacity=540,
        has_accessibility=False,
        has_air_conditioning=True,
        status=LocationStatus.DECLARADO,
        reliability_score=85.0,
    )

    db.add_all([loc1, loc2, loc3])
    await db.commit()
