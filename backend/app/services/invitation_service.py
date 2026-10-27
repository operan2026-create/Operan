import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mission import Mission
from app.models.network import Location, Professional, ProfessionalAvailability
from app.models.organization import Organization
from app.models.participant import (
    Invitation,
    InvitationPurpose,
    InvitationStatus,
    JourneyStatus,
    JourneyType,
    ParticipantConsent,
    ParticipantDataCategory,
    PersonProfile,
    PublicInvitation,
    PublicInvitationStatus,
    RepresentativeLinkStatus,
    RepresentativeSchoolLink,
)
from app.models.user import User, UserStatus
from app.schemas.participant import InvitationAcceptRequest
from app.security.blind_index import email_index
from app.security.encryption import crypto_manager
from app.security.hashing import get_password_hash
from app.services import account_service, audit_service


def hash_email(email: str) -> str:
    return email_index(email)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_expired(invitation: Invitation) -> bool:
    expires_at = _aware(invitation.expires_at)
    return expires_at is not None and expires_at <= _now()


def public_effective_status(invitation: PublicInvitation) -> PublicInvitationStatus:
    return _public_effective_status(invitation)


def _public_effective_status(invitation: PublicInvitation) -> PublicInvitationStatus:
    if invitation.status != PublicInvitationStatus.ACTIVE:
        return invitation.status
    if _aware(invitation.expires_at) <= _now():
        return PublicInvitationStatus.EXPIRED
    if invitation.max_uses is not None and invitation.uses_count >= invitation.max_uses:
        return PublicInvitationStatus.EXPIRED
    return PublicInvitationStatus.ACTIVE


def _public_id() -> str:
    return "USR-" + str(uuid.uuid4())[:8].upper()


def _normalize_categories(
    categories: Optional[list[ParticipantDataCategory]],
) -> list[str]:
    if not categories:
        return []
    seen = set()
    output = []
    for category in categories:
        value = category.value if hasattr(category, "value") else str(category)
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


async def _resolve_invitation_purpose(
    db: AsyncSession,
    *,
    purpose: InvitationPurpose,
    journey_type: JourneyType,
    mission_id: Optional[uuid.UUID],
    organization_id: Optional[uuid.UUID],
    location: Optional[Location],
) -> tuple[Optional[Mission], Optional[uuid.UUID]]:
    if purpose == InvitationPurpose.LOCATION_REPRESENTATIVE:
        if journey_type != JourneyType.LOCATIONS or location is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Convites de representante exigem uma escola/local vinculado.",
            )
    if purpose == InvitationPurpose.PROFESSIONAL_NETWORK:
        if journey_type != JourneyType.PROFESSIONALS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Convites de rede profissional usam a jornada de profissionais.",
            )
        if mission_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Convites de rede profissional nao podem apontar para missao.",
            )
    if purpose == InvitationPurpose.GLOBAL_REGISTRATION and mission_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Convites de cadastro global nao podem apontar para missao.",
        )

    if mission_id is None:
        if purpose == InvitationPurpose.MISSION_PARTICIPANT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Convites de participante de missao exigem a missao.",
            )
        return None, organization_id

    if purpose != InvitationPurpose.MISSION_PARTICIPANT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Somente convites de participante de missao podem apontar para missao.",
        )
    if journey_type != JourneyType.PROFESSIONALS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Convidados de missao usam a jornada de profissionais.",
        )
    mission = await db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missao nao encontrada."
        )
    mission_organization_id = mission.organization_id
    if mission_organization_id is None and mission.location_id:
        mission_location = await db.get(Location, mission.location_id)
        if mission_location is not None:
            mission_organization_id = mission_location.organization_id
    if (
        organization_id is not None
        and mission_organization_id is not None
        and organization_id != mission_organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A missao pertence a outra organizacao.",
        )
    return mission, organization_id or mission_organization_id


async def create_invitation(
    db: AsyncSession,
    *,
    email: str,
    journey_type: JourneyType,
    organization_id: Optional[uuid.UUID],
    location_id: Optional[uuid.UUID],
    creator,
    expires_in_days: int,
    purpose: InvitationPurpose = InvitationPurpose.GLOBAL_REGISTRATION,
    mission_id: Optional[uuid.UUID] = None,
    required_data_categories: Optional[list[ParticipantDataCategory]] = None,
    request: Optional[Request] = None,
) -> tuple[Invitation, str]:
    location: Optional[Location] = None
    organization: Optional[Organization] = None

    if location_id:
        location = (
            (await db.execute(select(Location).where(Location.id == location_id)))
            .scalars()
            .first()
        )
        if not location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Escola/local nao encontrado."
            )
        if journey_type != JourneyType.LOCATIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Local so pode ser vinculado a convite da jornada de representante.",
            )
        organization_id = location.organization_id

    if journey_type == JourneyType.LOCATIONS and location is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Convites da jornada de locais exigem uma escola/local vinculado.",
        )

    if organization_id:
        organization = (
            (await db.execute(select(Organization).where(Organization.id == organization_id)))
            .scalars()
            .first()
        )
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Organizacao nao existe."
            )

    if not creator.is_admin:
        if journey_type == JourneyType.LOCATIONS and not location:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Representantes so podem ser convidados por uma escola vinculada.",
            )
        if organization_id is None:
            organization_id = creator.primary_organization_id
        if not organization_id or not creator.is_manager_of(organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Voce so pode convidar para uma organizacao que gerencia.",
            )
        if journey_type == JourneyType.LOCATIONS and location_id:
            if location is None or location.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="A escola nao pertence a organizacao gerenciada.",
                )

    _mission, organization_id = await _resolve_invitation_purpose(
        db,
        purpose=purpose,
        journey_type=journey_type,
        mission_id=mission_id,
        organization_id=organization_id,
        location=location,
    )

    normalized_email = email.lower()
    raw_token = secrets.token_urlsafe(32)
    invitation = Invitation(
        token_hash=hash_token(raw_token),
        token_prefix=raw_token[:8],
        token_encrypted=crypto_manager.encrypt_data(raw_token),
        email_hash=hash_email(normalized_email),
        email_encrypted=crypto_manager.encrypt_data(normalized_email),
        journey_type=journey_type,
        purpose=purpose,
        mission_id=mission_id,
        required_data_categories=_normalize_categories(required_data_categories),
        organization_id=organization_id,
        location_id=location_id,
        created_by_user_id=creator.user.id,
        status=InvitationStatus.PENDING,
        expires_at=_now() + timedelta(days=expires_in_days),
    )
    db.add(invitation)
    await db.flush()
    audit_service.record(
        db,
        action="invitation.created",
        entity_type="Invitation",
        actor=creator.user,
        entity_id=str(invitation.id),
        organization_id=organization_id,
        details={
            "email": normalized_email,
            "journey_type": journey_type.value,
            "purpose": purpose.value,
            "mission_id": str(mission_id) if mission_id else None,
            "location_id": str(location_id) if location_id else None,
            "token_prefix": invitation.token_prefix,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(invitation)
    return invitation, raw_token


async def create_public_invitation(
    db: AsyncSession,
    *,
    journey_type: JourneyType,
    organization_id: Optional[uuid.UUID],
    location_id: Optional[uuid.UUID],
    label: Optional[str],
    creator,
    expires_in_days: int,
    max_uses: Optional[int],
    purpose: InvitationPurpose = InvitationPurpose.GLOBAL_REGISTRATION,
    mission_id: Optional[uuid.UUID] = None,
    required_data_categories: Optional[list[ParticipantDataCategory]] = None,
    request: Optional[Request] = None,
) -> tuple[PublicInvitation, str]:
    location: Optional[Location] = None
    organization: Optional[Organization] = None

    if location_id:
        location = (
            (await db.execute(select(Location).where(Location.id == location_id)))
            .scalars()
            .first()
        )
        if not location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Escola/local nao encontrado."
            )
        if journey_type != JourneyType.LOCATIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Local so pode ser vinculado a link da jornada de representante.",
            )
        organization_id = location.organization_id

    if journey_type == JourneyType.LOCATIONS and location is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Links da jornada de locais exigem uma escola/local vinculado.",
        )

    if organization_id:
        organization = (
            (await db.execute(select(Organization).where(Organization.id == organization_id)))
            .scalars()
            .first()
        )
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Organizacao nao existe."
            )

    if not creator.is_admin:
        if journey_type == JourneyType.LOCATIONS and not location:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Representantes so podem ser convidados por uma escola vinculada.",
            )
        if organization_id is None:
            organization_id = creator.primary_organization_id
        if not organization_id or not creator.is_manager_of(organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Voce so pode criar links para uma organizacao que gerencia.",
            )
        if journey_type == JourneyType.LOCATIONS and location_id:
            if location is None or location.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="A escola nao pertence a organizacao gerenciada.",
                )

    _mission, organization_id = await _resolve_invitation_purpose(
        db,
        purpose=purpose,
        journey_type=journey_type,
        mission_id=mission_id,
        organization_id=organization_id,
        location=location,
    )

    raw_token = secrets.token_urlsafe(32)
    invitation = PublicInvitation(
        token_hash=hash_token(raw_token),
        token_prefix=raw_token[:8],
        token_encrypted=crypto_manager.encrypt_data(raw_token),
        label=label,
        journey_type=journey_type,
        purpose=purpose,
        mission_id=mission_id,
        required_data_categories=_normalize_categories(required_data_categories),
        organization_id=organization_id,
        location_id=location_id,
        created_by_user_id=creator.user.id,
        status=PublicInvitationStatus.ACTIVE,
        expires_at=_now() + timedelta(days=expires_in_days),
        max_uses=max_uses,
        uses_count=0,
    )
    db.add(invitation)
    await db.flush()
    audit_service.record(
        db,
        action="public_invitation.created",
        entity_type="PublicInvitation",
        actor=creator.user,
        entity_id=str(invitation.id),
        organization_id=organization_id,
        details={
            "journey_type": journey_type.value,
            "purpose": purpose.value,
            "mission_id": str(mission_id) if mission_id else None,
            "location_id": str(location_id) if location_id else None,
            "max_uses": max_uses,
            "token_prefix": invitation.token_prefix,
        },
        request=request,
    )
    await db.commit()
    stored = await get_public_by_token(db, raw_token)
    return stored, raw_token


async def get_public_by_token(
    db: AsyncSession, token: str, *, lock: bool = False
) -> Optional[PublicInvitation]:
    if not token:
        return None
    query = (
        select(PublicInvitation)
        .options(
            selectinload(PublicInvitation.organization),
            selectinload(PublicInvitation.location),
        )
        .where(PublicInvitation.token_hash == hash_token(token))
    )
    if lock:
        query = query.with_for_update()
    return (await db.execute(query)).scalars().first()


async def validate_public_invitation(
    db: AsyncSession, token: str, current_user: Optional[User] = None
) -> dict:
    invitation = await get_public_by_token(db, token)
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link publico invalido ou inexistente.",
        )
    effective_status = _public_effective_status(invitation)
    return {
        "valid": effective_status == PublicInvitationStatus.ACTIVE,
        "status": effective_status,
        "label": invitation.label,
        "journey_type": invitation.journey_type,
        "purpose": invitation.purpose,
        "mission_id": invitation.mission_id,
        "required_data_categories": invitation.required_data_categories or [],
        "organization_id": invitation.organization_id,
        "organization_name": invitation.organization.name if invitation.organization else None,
        "location_id": invitation.location_id,
        "location_name": invitation.location.name if invitation.location else None,
        "expires_at": invitation.expires_at,
        "max_uses": invitation.max_uses,
        "uses_count": invitation.uses_count,
        "requires_account": current_user is None,
    }


async def list_public_invitations(
    db: AsyncSession, context
) -> list[PublicInvitation]:
    query = (
        select(PublicInvitation)
        .options(
            selectinload(PublicInvitation.organization),
            selectinload(PublicInvitation.location),
        )
        .order_by(PublicInvitation.created_at.desc())
    )
    if not context.is_admin:
        org_ids = context.client_organization_ids
        if not org_ids:
            return []
        query = query.where(PublicInvitation.organization_id.in_(org_ids))
    return list((await db.execute(query)).scalars().all())


async def revoke_public_invitation(
    db: AsyncSession,
    invitation_id: uuid.UUID,
    context,
    request: Optional[Request] = None,
) -> PublicInvitation:
    invitation = (
        (
            await db.execute(
                select(PublicInvitation)
                .options(
                    selectinload(PublicInvitation.organization),
                    selectinload(PublicInvitation.location),
                )
                .where(PublicInvitation.id == invitation_id)
            )
        )
        .scalars()
        .first()
    )
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Link publico nao encontrado."
        )
    if not context.is_admin:
        if (
            not invitation.organization_id
            or not context.is_manager_of(invitation.organization_id)
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    if invitation.status != PublicInvitationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este link publico nao esta mais ativo.",
        )
    invitation.status = PublicInvitationStatus.REVOKED
    invitation.revoked_at = _now()
    audit_service.record(
        db,
        action="public_invitation.revoked",
        entity_type="PublicInvitation",
        actor=context.user,
        entity_id=str(invitation.id),
        organization_id=invitation.organization_id,
        request=request,
    )
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def accept_public_invitation(
    db: AsyncSession,
    *,
    token: str,
    payload: InvitationAcceptRequest,
    current_user: Optional[User] = None,
    request: Optional[Request] = None,
) -> tuple[User, PersonProfile]:
    public_invitation = await get_public_by_token(db, token, lock=True)
    if not public_invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link publico invalido ou inexistente.",
        )
    if _public_effective_status(public_invitation) != PublicInvitationStatus.ACTIVE:
        if _public_effective_status(public_invitation) == PublicInvitationStatus.EXPIRED:
            public_invitation.status = PublicInvitationStatus.EXPIRED
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este link publico expirou ou nao esta mais disponivel.",
        )
    if not payload.privacy_consent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="E necessario aceitar a politica de privacidade e o tratamento de dados.",
        )
    payload_email = str(payload.email).lower() if payload.email else None
    current_email = (
        crypto_manager.decrypt_data(current_user.email_encrypted).lower()
        if current_user
        else None
    )
    if current_user and (not payload_email or payload_email == current_email):
        email = current_email
    else:
        if not payload_email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Informe o e-mail para criar sua conta.",
            )
        email = payload_email
        existing_user = (
            (await db.execute(select(User).where(User.email_hash == hash_email(email))))
            .scalars()
            .first()
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ja existe uma conta com este e-mail. Faca login para aceitar o convite.",
            )
        current_user = None

    raw_token = secrets.token_urlsafe(32)
    synthetic = Invitation(
        token_hash=hash_token(raw_token),
        token_prefix=raw_token[:8],
        token_encrypted=None,
        email_hash=hash_email(email),
        email_encrypted=crypto_manager.encrypt_data(email),
        journey_type=public_invitation.journey_type,
        purpose=public_invitation.purpose,
        mission_id=public_invitation.mission_id,
        required_data_categories=list(public_invitation.required_data_categories or []),
        organization_id=public_invitation.organization_id,
        location_id=public_invitation.location_id,
        created_by_user_id=public_invitation.created_by_user_id,
        status=InvitationStatus.PENDING,
        expires_at=public_invitation.expires_at,
    )
    db.add(synthetic)
    await db.flush()

    public_invitation.uses_count += 1
    if (
        public_invitation.max_uses is not None
        and public_invitation.uses_count >= public_invitation.max_uses
    ):
        public_invitation.status = PublicInvitationStatus.EXPIRED

    user, profile = await accept_invitation(
        db,
        token=raw_token,
        payload=payload,
        current_user=current_user,
        request=request,
        source_public_invitation_id=public_invitation.id,
    )
    audit_service.record(
        db,
        action="public_invitation.accepted",
        entity_type="PublicInvitation",
        actor=user,
        entity_id=str(public_invitation.id),
        organization_id=public_invitation.organization_id,
        details={
            "journey_type": public_invitation.journey_type.value,
            "user_public_id": user.public_id,
            "uses_count": public_invitation.uses_count,
        },
        request=request,
    )
    await db.commit()
    return user, profile


async def get_by_token(db: AsyncSession, token: str) -> Optional[Invitation]:
    if not token:
        return None
    return (
        (
            await db.execute(
                select(Invitation)
                .options(
                    selectinload(Invitation.organization),
                    selectinload(Invitation.location),
                )
                .where(Invitation.token_hash == hash_token(token))
            )
        )
        .scalars()
        .first()
    )


async def validate_invitation(db: AsyncSession, token: str) -> dict:
    invitation = await get_by_token(db, token)
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Convite invalido ou inexistente."
        )
    existing_user = (
        (await db.execute(select(User).where(User.email_hash == invitation.email_hash)))
        .scalars()
        .first()
    )
    effective_status = invitation.status
    if invitation.status == InvitationStatus.PENDING and _is_expired(invitation):
        effective_status = InvitationStatus.EXPIRED
    return {
        "valid": effective_status == InvitationStatus.PENDING,
        "status": effective_status,
        "email": crypto_manager.decrypt_data(invitation.email_encrypted),
        "journey_type": invitation.journey_type,
        "purpose": invitation.purpose,
        "mission_id": invitation.mission_id,
        "required_data_categories": invitation.required_data_categories or [],
        "organization_id": invitation.organization_id,
        "organization_name": invitation.organization.name if invitation.organization else None,
        "location_id": invitation.location_id,
        "location_name": invitation.location.name if invitation.location else None,
        "expires_at": invitation.expires_at,
        "requires_account": existing_user is None,
    }


async def list_invitations(db: AsyncSession, context) -> list[Invitation]:
    query = (
        select(Invitation)
        .options(
            selectinload(Invitation.organization),
            selectinload(Invitation.location),
        )
        .order_by(Invitation.created_at.desc())
    )
    if not context.is_admin:
        org_ids = context.client_organization_ids
        if not org_ids:
            return []
        query = query.where(Invitation.organization_id.in_(org_ids))
    return list((await db.execute(query)).scalars().all())


async def revoke_invitation(
    db: AsyncSession,
    invitation_id: uuid.UUID,
    context,
    request: Optional[Request] = None,
) -> Invitation:
    invitation = (
        (
            await db.execute(
                select(Invitation)
                .options(
                    selectinload(Invitation.organization),
                    selectinload(Invitation.location),
                )
                .where(Invitation.id == invitation_id)
            )
        )
        .scalars()
        .first()
    )
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convite nao encontrado.")
    if not context.is_admin:
        if not invitation.organization_id or not context.is_manager_of(
            invitation.organization_id
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somente convites pendentes podem ser revogados.",
        )
    invitation.status = InvitationStatus.REVOKED
    invitation.revoked_at = _now()
    audit_service.record(
        db,
        action="invitation.revoked",
        entity_type="Invitation",
        actor=context.user,
        entity_id=str(invitation.id),
        organization_id=invitation.organization_id,
        request=request,
    )
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def regenerate_token(
    db: AsyncSession,
    invitation_id: uuid.UUID,
    context,
    request: Optional[Request] = None,
) -> tuple[Invitation, str]:
    invitation = (
        (
            await db.execute(
                select(Invitation)
                .options(
                    selectinload(Invitation.organization),
                    selectinload(Invitation.location),
                )
                .where(Invitation.id == invitation_id)
            )
        )
        .scalars()
        .first()
    )
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Convite nao encontrado."
        )
    if not context.is_admin:
        if not invitation.organization_id or not context.is_manager_of(
            invitation.organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado."
            )
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somente convites pendentes podem ter o link regenerado.",
        )
    raw_token = secrets.token_urlsafe(32)
    invitation.token_hash = hash_token(raw_token)
    invitation.token_prefix = raw_token[:8]
    invitation.token_encrypted = crypto_manager.encrypt_data(raw_token)
    audit_service.record(
        db,
        action="invitation.link_regenerated",
        entity_type="Invitation",
        actor=context.user,
        entity_id=str(invitation.id),
        organization_id=invitation.organization_id,
        details={"token_prefix": invitation.token_prefix},
        request=request,
    )
    await db.commit()
    await db.refresh(invitation)
    return invitation, raw_token


async def _ensure_professional_record(
    db: AsyncSession, user: User, profile: PersonProfile
) -> Professional:
    professional = (
        (await db.execute(select(Professional).where(Professional.user_id == user.id)))
        .scalars()
        .first()
    )
    if professional:
        return professional
    professional = Professional(
        user_id=user.id,
        full_name=profile.full_name,
        cpf_hash=profile.cpf_hash,
        cpf_encrypted=profile.cpf_encrypted,
        phone_encrypted=profile.phone_encrypted,
        city=profile.city,
        state=profile.state,
        operational_radius_km=30,
        availability_status=ProfessionalAvailability.AVAILABLE,
        reputation_score=100.0,
    )
    db.add(professional)
    await db.flush()
    return professional


async def accept_invitation(
    db: AsyncSession,
    *,
    token: str,
    payload: InvitationAcceptRequest,
    current_user: Optional[User] = None,
    request: Optional[Request] = None,
    source_public_invitation_id: Optional[uuid.UUID] = None,
) -> tuple[User, PersonProfile]:
    invitation = await get_by_token(db, token)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convite invalido.")
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Este convite nao esta mais disponivel."
        )
    if _is_expired(invitation):
        invitation.status = InvitationStatus.EXPIRED
        await db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este convite expirou.")
    if not payload.privacy_consent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="E necessario aceitar a politica de privacidade e o tratamento de dados.",
        )

    email = crypto_manager.decrypt_data(invitation.email_encrypted)
    user_by_email = (
        (await db.execute(select(User).where(User.email_hash == invitation.email_hash)))
        .scalars()
        .first()
    )

    if current_user:
        if current_user.email_hash != invitation.email_hash:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Este convite pertence a outro e-mail.",
            )
        user = current_user
        # An invitation may activate a PENDING account, but it must never
        # reactivate an account that was blocked by an administrator.
        if user.status == UserStatus.PENDING:
            user.status = UserStatus.ACTIVE
        elif user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Conta indisponivel. Procure o suporte da plataforma.",
            )
    else:
        if user_by_email is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ja existe uma conta com este e-mail. Faca login para aceitar o convite.",
            )
        if not payload.password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Senha obrigatoria para criar a conta.",
            )
        user = User(
            public_id=_public_id(),
            email_hash=invitation.email_hash,
            email_encrypted=crypto_manager.encrypt_data(email.lower()),
            password_hash=get_password_hash(payload.password),
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        await db.flush()

    profile = await account_service.get_profile(db, user.id)
    if not profile:
        legacy = (
            (await db.execute(select(Professional).where(Professional.user_id == user.id)))
            .scalars()
            .first()
        )
        profile = await account_service.ensure_profile_from_legacy(db, user, legacy)
    if profile:
        await account_service.update_profile_from_invite(db, user, profile, payload)
    else:
        profile = await account_service.create_profile_from_invite(db, user, payload)

    await account_service.ensure_journey(
        db,
        user.id,
        invitation.journey_type,
        status=JourneyStatus.ACTIVE,
        source_invitation_id=invitation.id,
    )

    if invitation.journey_type == JourneyType.PROFESSIONALS:
        await _ensure_professional_record(db, user, profile)

    if invitation.journey_type == JourneyType.LOCATIONS and invitation.location_id:
        link = (
            (
                await db.execute(
                    select(RepresentativeSchoolLink).where(
                        RepresentativeSchoolLink.representative_user_id == user.id,
                        RepresentativeSchoolLink.location_id == invitation.location_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if link:
            link.status = RepresentativeLinkStatus.ACTIVE
            link.invitation_id = invitation.id
        else:
            db.add(
                RepresentativeSchoolLink(
                    representative_user_id=user.id,
                    location_id=invitation.location_id,
                    status=RepresentativeLinkStatus.ACTIVE,
                    invitation_id=invitation.id,
                    created_by_user_id=invitation.created_by_user_id,
                )
            )

    if invitation.organization_id:
        await account_service.ensure_participant_client_link(
            db,
            user=user,
            organization_id=invitation.organization_id,
            purpose=(
                invitation.purpose.value
                if invitation.purpose is not None
                else "OPERATIONAL"
            ),
            source_invitation_id=(
                None if source_public_invitation_id else invitation.id
            ),
            source_public_invitation_id=source_public_invitation_id,
            source_mission_id=invitation.mission_id,
            created_by_user_id=invitation.created_by_user_id,
        )

    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = _now()
    invitation.accepted_by_user_id = user.id

    ip_address, user_agent = audit_service.request_metadata(request)
    db.add(
        ParticipantConsent(
            user_id=user.id,
            consent_type="PRIVACY_POLICY",
            policy_version=payload.consent_version,
            purpose="Cadastro e execucao de atividades operacionais",
            legal_basis="CONSENTIMENTO",
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    audit_service.record(
        db,
        action="invitation.accepted",
        entity_type="Invitation",
        actor=user,
        entity_id=str(invitation.id),
        organization_id=invitation.organization_id,
        details={
            "email": email,
            "journey_type": invitation.journey_type.value,
            "user_public_id": user.public_id,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    await db.refresh(profile)
    return user, profile
