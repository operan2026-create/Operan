import base64
import binascii
import hashlib
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.network import Professional
from app.models.participant import (
    JourneyEnrollment,
    JourneyStatus,
    JourneyType,
    ParticipantBankAccount,
    ParticipantBankAccountStatus,
    ParticipantClientLink,
    ParticipantClientLinkStatus,
    ParticipantFamilyMember,
    PersonProfile,
    ProfessionalQualification,
)
from app.models.user import User
from app.schemas.participant import (
    AccountResponse,
    InvitationAcceptRequest,
    JourneyResponse,
    JourneyStatusUpdate,
    AvatarUpdate,
    BankAccountCreate,
    BankAccountResponse,
    BankAccountUpdate,
    FamilyMemberCreate,
    FamilyMemberResponse,
    FamilyMemberUpdate,
    PersonProfileResponse,
    PersonProfileUpdate,
    QualificationResponse,
    mask_account_number,
    mask_cpf,
    mask_generic,
    mask_phone,
    normalize_cpf,
)
from app.core.config import settings
from app.security.blind_index import cpf_index, rg_index
from app.security.encryption import crypto_manager
from app.services import audit_service

AVATAR_MIME_TYPES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _profile_complete(profile: PersonProfile) -> bool:
    return all(
        [
            bool(profile.full_name),
            bool(profile.phone_encrypted),
            bool(profile.city),
            bool(profile.state),
            profile.birth_date is not None,
            bool(profile.address_street),
            bool(profile.avatar_data),
        ]
    )


def decode_avatar(
    avatar_base64: Optional[str], avatar_mime_type: Optional[str]
) -> Optional[tuple[str, str, str]]:
    if not avatar_base64:
        return None
    raw_base64 = avatar_base64.strip()
    mime = (avatar_mime_type or "").lower().strip()
    if raw_base64.startswith("data:"):
        header, _, raw_base64 = raw_base64.partition(",")
        if not mime and header.startswith("data:"):
            mime = header[5:].split(";", 1)[0].lower()
    try:
        content = base64.b64decode(raw_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Foto de perfil invalida.",
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Foto de perfil vazia.",
        )
    if len(content) > settings.MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Foto de perfil excede o limite de 5 MB.",
        )
    if mime not in AVATAR_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Foto de perfil deve ser JPEG ou PNG.",
        )
    if not any(content.startswith(signature) for signature in AVATAR_MIME_TYPES[mime]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Conteudo da foto nao corresponde ao formato declarado.",
        )
    canonical = base64.b64encode(content).decode("ascii")
    return canonical, mime, hashlib.sha256(content).hexdigest()


def _set_avatar(
    profile: PersonProfile,
    avatar_base64: Optional[str],
    avatar_mime_type: Optional[str],
) -> None:
    decoded = decode_avatar(avatar_base64, avatar_mime_type)
    if not decoded:
        return
    profile.avatar_data, profile.avatar_mime_type, profile.avatar_sha256 = decoded
    profile.avatar_updated_at = _now()


def avatar_bytes(profile: PersonProfile) -> Optional[bytes]:
    if not profile.avatar_data:
        return None
    try:
        return base64.b64decode(profile.avatar_data, validate=True)
    except (ValueError, binascii.Error):
        return None


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> Optional[PersonProfile]:
    return (
        (await db.execute(select(PersonProfile).where(PersonProfile.user_id == user_id)))
        .scalars()
        .first()
    )


async def ensure_profile_from_legacy(
    db: AsyncSession, user: User, professional: Optional[Professional]
) -> Optional[PersonProfile]:
    profile = await get_profile(db, user.id)
    if profile or not professional:
        return profile
    profile = PersonProfile(
        user_id=user.id,
        full_name=professional.full_name,
        cpf_hash=professional.cpf_hash,
        cpf_encrypted=professional.cpf_encrypted,
        phone_encrypted=professional.phone_encrypted,
        city=professional.city,
        state=professional.state,
        profile_completed=False,
    )
    db.add(profile)
    await db.flush()
    return profile


async def create_profile(
    db: AsyncSession,
    user: User,
    *,
    full_name: str,
    cpf: str,
    phone: str,
    city: str,
    state: str,
    social_name: Optional[str] = None,
    rg: Optional[str] = None,
    birth_date: Optional[date] = None,
    gender: Optional[str] = None,
    zip_code: Optional[str] = None,
    address_street: Optional[str] = None,
    address_number: Optional[str] = None,
    address_complement: Optional[str] = None,
    address_neighborhood: Optional[str] = None,
    emergency_contact_name: Optional[str] = None,
    emergency_contact_phone: Optional[str] = None,
    bio: Optional[str] = None,
    avatar_base64: Optional[str] = None,
    avatar_mime_type: Optional[str] = None,
) -> PersonProfile:
    cpf_clean = normalize_cpf(cpf)
    cpf_hash = cpf_index(cpf_clean)
    duplicate = (
        (await db.execute(select(PersonProfile).where(PersonProfile.cpf_hash == cpf_hash)))
        .scalars()
        .first()
    )
    legacy_duplicate = (
        (await db.execute(select(Professional).where(Professional.cpf_hash == cpf_hash)))
        .scalars()
        .first()
    )
    if duplicate or legacy_duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este CPF ja esta cadastrado na plataforma.",
        )
    profile = PersonProfile(
        user_id=user.id,
        full_name=full_name,
        social_name=social_name,
        cpf_hash=cpf_hash,
        cpf_encrypted=crypto_manager.encrypt_data(cpf_clean),
        phone_encrypted=crypto_manager.encrypt_data(phone),
        rg_encrypted=crypto_manager.encrypt_data(rg) if rg else None,
        rg_hash=rg_index(rg) if rg else None,
        birth_date=birth_date,
        gender=gender,
        city=city,
        state=state.upper(),
        zip_code=zip_code,
        address_street=address_street,
        address_number=address_number,
        address_complement=address_complement,
        address_neighborhood=address_neighborhood,
        emergency_contact_name=emergency_contact_name,
        emergency_contact_phone_encrypted=(
            crypto_manager.encrypt_data(emergency_contact_phone)
            if emergency_contact_phone
            else None
        ),
        bio=bio,
        profile_completed=False,
    )
    _set_avatar(profile, avatar_base64, avatar_mime_type)
    profile.profile_completed = _profile_complete(profile)
    db.add(profile)
    await db.flush()
    return profile


async def create_profile_from_invite(
    db: AsyncSession, user: User, payload: InvitationAcceptRequest
) -> PersonProfile:
    required = {
        "full_name": payload.full_name,
        "cpf": payload.cpf,
        "phone": payload.phone,
        "city": payload.city,
        "state": payload.state,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dados obrigatorios ausentes: " + ", ".join(missing),
        )
    if not payload.avatar_base64:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Foto de perfil obrigatoria.",
        )
    return await create_profile(
        db,
        user,
        full_name=payload.full_name or "",
        cpf=payload.cpf or "",
        phone=payload.phone or "",
        city=payload.city or "",
        state=payload.state or "",
        social_name=payload.social_name,
        rg=payload.rg,
        birth_date=payload.birth_date,
        gender=payload.gender,
        zip_code=payload.zip_code,
        address_street=payload.address_street,
        address_number=payload.address_number,
        address_complement=payload.address_complement,
        address_neighborhood=payload.address_neighborhood,
        emergency_contact_name=payload.emergency_contact_name,
        emergency_contact_phone=payload.emergency_contact_phone,
        bio=payload.bio,
        avatar_base64=payload.avatar_base64,
        avatar_mime_type=payload.avatar_mime_type,
    )


async def update_profile_from_invite(
    db: AsyncSession,
    user: User,
    profile: PersonProfile,
    payload: InvitationAcceptRequest,
) -> None:
    data = payload.model_dump(exclude_unset=True)
    for field in (
        "full_name",
        "social_name",
        "birth_date",
        "gender",
        "city",
        "state",
        "zip_code",
        "address_street",
        "address_number",
        "address_complement",
        "address_neighborhood",
        "emergency_contact_name",
        "bio",
    ):
        if field in data and data[field] is not None:
            setattr(profile, field, data[field])
    if data.get("phone"):
        profile.phone_encrypted = crypto_manager.encrypt_data(data["phone"])
    if data.get("rg"):
        profile.rg_encrypted = crypto_manager.encrypt_data(data["rg"])
        profile.rg_hash = rg_index(data["rg"])
    if data.get("emergency_contact_phone"):
        profile.emergency_contact_phone_encrypted = crypto_manager.encrypt_data(
            data["emergency_contact_phone"]
        )
    _set_avatar(profile, payload.avatar_base64, payload.avatar_mime_type)
    profile.profile_completed = _profile_complete(profile)
    if not profile.avatar_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Foto de perfil obrigatoria.",
        )
    await db.flush()


def profile_response(user: User, profile: PersonProfile) -> PersonProfileResponse:
    cpf = crypto_manager.decrypt_data(profile.cpf_encrypted)
    phone = crypto_manager.decrypt_data(profile.phone_encrypted)
    rg = crypto_manager.decrypt_data(profile.rg_encrypted) if profile.rg_encrypted else None
    emergency_phone = (
        crypto_manager.decrypt_data(profile.emergency_contact_phone_encrypted)
        if profile.emergency_contact_phone_encrypted
        else None
    )
    return PersonProfileResponse(
        user_id=user.id,
        public_id=user.public_id,
        email=user.email,
        full_name=profile.full_name,
        social_name=profile.social_name,
        cpf_masked=mask_cpf(cpf),
        phone_masked=mask_phone(phone),
        rg_masked=mask_generic(rg, 2) if rg else None,
        birth_date=profile.birth_date,
        gender=profile.gender,
        city=profile.city,
        state=profile.state,
        zip_code=profile.zip_code,
        address_street=profile.address_street,
        address_number=profile.address_number,
        address_complement=profile.address_complement,
        address_neighborhood=profile.address_neighborhood,
        emergency_contact_name=profile.emergency_contact_name,
        emergency_contact_phone_masked=mask_phone(emergency_phone) if emergency_phone else None,
        bio=profile.bio,
        has_avatar=bool(profile.avatar_data),
        avatar_url=(
            f"/api/v1/account/avatar?v={int(profile.avatar_updated_at.timestamp())}"
            if profile.avatar_data and profile.avatar_updated_at
            else ("/api/v1/account/avatar" if profile.avatar_data else None)
        ),
        profile_completed=profile.profile_completed,
        cadastral_status=profile.cadastral_status,
        cadastral_status_updated_at=profile.cadastral_status_updated_at,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


async def update_profile(
    db: AsyncSession,
    user: User,
    profile: PersonProfile,
    payload: PersonProfileUpdate,
    request: Optional[Request] = None,
) -> PersonProfileResponse:
    data = payload.model_dump(exclude_unset=True)
    changed = sorted(data.keys())
    for field, value in data.items():
        if field == "phone":
            profile.phone_encrypted = crypto_manager.encrypt_data(value)
        elif field == "rg":
            if value:
                profile.rg_encrypted = crypto_manager.encrypt_data(value)
                profile.rg_hash = rg_index(value)
            else:
                profile.rg_encrypted = None
                profile.rg_hash = None
        elif field == "emergency_contact_phone":
            profile.emergency_contact_phone_encrypted = (
                crypto_manager.encrypt_data(value) if value else None
            )
        else:
            setattr(profile, field, value)
    profile.profile_completed = _profile_complete(profile)
    audit_service.record(
        db,
        action="account.profile_updated",
        entity_type="PersonProfile",
        actor=user,
        entity_id=str(profile.id),
        details={"fields": changed},
        request=request,
    )
    await db.commit()
    await db.refresh(profile)
    return profile_response(user, profile)


async def update_avatar(
    db: AsyncSession,
    user: User,
    profile: PersonProfile,
    payload: AvatarUpdate,
    request: Optional[Request] = None,
) -> PersonProfileResponse:
    _set_avatar(profile, payload.avatar_base64, payload.avatar_mime_type)
    if not profile.avatar_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Foto de perfil obrigatoria.",
        )
    profile.profile_completed = _profile_complete(profile)
    audit_service.record(
        db,
        action="account.avatar_updated",
        entity_type="PersonProfile",
        actor=user,
        entity_id=str(profile.id),
        details={"sha256": profile.avatar_sha256},
        request=request,
    )
    await db.commit()
    await db.refresh(profile)
    return profile_response(user, profile)


BANK_MUTABLE_FIELDS = {
    "bank_code",
    "bank_name",
    "branch",
    "account_number",
    "account_type",
    "holder_name",
    "holder_cpf",
    "pix_key_type",
    "pix_key",
}
BANK_REQUIRED_FIELDS = {
    "bank_code",
    "bank_name",
    "branch",
    "account_number",
    "account_type",
    "holder_name",
}
FAMILY_REQUIRED_FIELDS = {"full_name", "kinship"}


def _bank_fingerprint(bank_code: str, branch: str, account_number: str) -> str:
    raw = "|".join(
        [
            (bank_code or "").strip().upper(),
            "".join(filter(str.isdigit, branch or "")),
            "".join(filter(str.isdigit, account_number or "")),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _cpf_hash(cpf: Optional[str]) -> Optional[str]:
    if not cpf:
        return None
    return cpf_index(cpf)


async def ensure_participant_client_link(
    db: AsyncSession,
    *,
    user: User,
    organization_id: uuid.UUID,
    purpose: str = "OPERATIONAL",
    status: ParticipantClientLinkStatus = ParticipantClientLinkStatus.ACTIVE,
    source_invitation_id: Optional[uuid.UUID] = None,
    source_public_invitation_id: Optional[uuid.UUID] = None,
    source_mission_id: Optional[uuid.UUID] = None,
    created_by_user_id: Optional[uuid.UUID] = None,
) -> ParticipantClientLink:
    link = (
        (
            await db.execute(
                select(ParticipantClientLink).where(
                    ParticipantClientLink.user_id == user.id,
                    ParticipantClientLink.organization_id == organization_id,
                )
            )
        )
        .scalars()
        .first()
    )
    if link:
        link.status = status
        link.purpose = purpose
        link.source_mission_id = source_mission_id or link.source_mission_id
        link.ended_at = None
        if source_public_invitation_id:
            link.source_public_invitation_id = source_public_invitation_id
        if source_invitation_id:
            link.source_invitation_id = source_invitation_id
        return link
    link = ParticipantClientLink(
        user_id=user.id,
        organization_id=organization_id,
        purpose=purpose,
        status=status,
        source_invitation_id=source_invitation_id,
        source_public_invitation_id=source_public_invitation_id,
        source_mission_id=source_mission_id,
        created_by_user_id=created_by_user_id,
        valid_from=_now(),
    )
    db.add(link)
    return link


async def list_bank_accounts(
    db: AsyncSession, user_id: uuid.UUID
) -> list[ParticipantBankAccount]:
    return list(
        (
            await db.execute(
                select(ParticipantBankAccount)
                .where(ParticipantBankAccount.user_id == user_id)
                .order_by(
                    ParticipantBankAccount.is_primary.desc(),
                    ParticipantBankAccount.created_at.asc(),
                )
            )
        )
        .scalars()
        .all()
    )


async def _clear_primary_bank(
    db: AsyncSession, user_id: uuid.UUID, *, except_id: Optional[uuid.UUID] = None
) -> None:
    query = update(ParticipantBankAccount).where(
        ParticipantBankAccount.user_id == user_id,
        ParticipantBankAccount.is_primary.is_(True),
    )
    if except_id:
        query = query.where(ParticipantBankAccount.id != except_id)
    await db.execute(query.values(is_primary=False))


async def create_bank_account(
    db: AsyncSession,
    user: User,
    payload: BankAccountCreate,
    request: Optional[Request] = None,
) -> ParticipantBankAccount:
    fingerprint = _bank_fingerprint(
        payload.bank_code, payload.branch, payload.account_number
    )
    duplicate = (
        (
            await db.execute(
                select(ParticipantBankAccount).where(
                    ParticipantBankAccount.user_id == user.id,
                    ParticipantBankAccount.account_fingerprint == fingerprint,
                )
            )
        )
        .scalars()
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta conta bancaria ja esta cadastrada.",
        )
    accounts = await list_bank_accounts(db, user.id)
    is_primary = payload.is_primary or not accounts
    if is_primary:
        await _clear_primary_bank(db, user.id)
    account = ParticipantBankAccount(
        user_id=user.id,
        bank_code=payload.bank_code.strip(),
        bank_name=payload.bank_name.strip(),
        branch=payload.branch.strip(),
        account_number=payload.account_number.strip(),
        account_type=payload.account_type,
        holder_name=payload.holder_name.strip(),
        holder_cpf=payload.holder_cpf,
        holder_cpf_hash=_cpf_hash(payload.holder_cpf),
        pix_key_type=payload.pix_key_type,
        pix_key=payload.pix_key.strip() if payload.pix_key else None,
        account_fingerprint=fingerprint,
        is_primary=is_primary,
    )
    db.add(account)
    audit_service.record(
        db,
        action="account.bank_account_created",
        entity_type="ParticipantBankAccount",
        actor=user,
        details={
            "bank_code": account.bank_code,
            "account_type": account.account_type,
            "is_primary": account.is_primary,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(account)
    return account


async def update_bank_account(
    db: AsyncSession,
    user: User,
    account_id: uuid.UUID,
    payload: BankAccountUpdate,
    request: Optional[Request] = None,
) -> ParticipantBankAccount:
    account = (
        (
            await db.execute(
                select(ParticipantBankAccount).where(
                    ParticipantBankAccount.id == account_id,
                    ParticipantBankAccount.user_id == user.id,
                )
            )
        )
        .scalars()
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conta bancaria nao encontrada.",
        )
    data = payload.model_dump(exclude_unset=True)
    changed = sorted(data.keys())
    for field in BANK_REQUIRED_FIELDS & set(data):
        if data[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Campo obrigatorio nao pode ser vazio: {field}.",
            )
    bank_code = data.get("bank_code", account.bank_code)
    branch = data.get("branch", account.branch)
    account_number = data.get("account_number", account.account_number)
    fingerprint = _bank_fingerprint(bank_code, branch, account_number)
    if fingerprint != account.account_fingerprint:
        duplicate = (
            (
                await db.execute(
                    select(ParticipantBankAccount).where(
                        ParticipantBankAccount.user_id == user.id,
                        ParticipantBankAccount.account_fingerprint == fingerprint,
                        ParticipantBankAccount.id != account.id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta conta bancaria ja esta cadastrada.",
            )

    if data.get("is_primary") is True:
        await _clear_primary_bank(db, user.id, except_id=account.id)

    for field in BANK_MUTABLE_FIELDS & set(data):
        value = data[field]
        if field in {"bank_code", "bank_name", "branch", "account_number", "holder_name"}:
            value = value.strip()
        elif field == "pix_key":
            value = value.strip() if value else None
        setattr(account, field, value)
        if field == "holder_cpf":
            account.holder_cpf_hash = _cpf_hash(value)
    if "is_primary" in data and data["is_primary"] is not None:
        account.is_primary = data["is_primary"]
    account.account_fingerprint = fingerprint

    if BANK_MUTABLE_FIELDS & set(data):
        account.status = ParticipantBankAccountStatus.PENDING
        account.verified_by_user_id = None
        account.verified_at = None
        account.rejection_reason = None

    audit_service.record(
        db,
        action="account.bank_account_updated",
        entity_type="ParticipantBankAccount",
        actor=user,
        entity_id=str(account.id),
        details={
            "fields": changed,
            "status": account.status.value,
            "is_primary": account.is_primary,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(account)
    return account


async def delete_bank_account(
    db: AsyncSession,
    user: User,
    account_id: uuid.UUID,
    request: Optional[Request] = None,
) -> None:
    account = (
        (
            await db.execute(
                select(ParticipantBankAccount).where(
                    ParticipantBankAccount.id == account_id,
                    ParticipantBankAccount.user_id == user.id,
                )
            )
        )
        .scalars()
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conta bancaria nao encontrada.",
        )
    was_primary = account.is_primary
    await db.delete(account)
    if was_primary:
        remaining = (
            (
                await db.execute(
                    select(ParticipantBankAccount)
                    .where(
                        ParticipantBankAccount.user_id == user.id,
                        ParticipantBankAccount.id != account_id,
                    )
                    .order_by(ParticipantBankAccount.created_at.asc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if remaining:
            remaining.is_primary = True
    audit_service.record(
        db,
        action="account.bank_account_deleted",
        entity_type="ParticipantBankAccount",
        actor=user,
        entity_id=str(account_id),
        request=request,
    )
    await db.commit()


def bank_account_response(account: ParticipantBankAccount) -> BankAccountResponse:
    holder_cpf = account.holder_cpf
    return BankAccountResponse(
        id=account.id,
        bank_code=account.bank_code,
        bank_name=account.bank_name,
        branch=account.branch,
        account_number_masked=mask_account_number(account.account_number),
        account_type=account.account_type,
        holder_name=account.holder_name,
        holder_cpf_masked=mask_cpf(holder_cpf) if holder_cpf else None,
        pix_key_type=account.pix_key_type,
        pix_key_masked=mask_generic(account.pix_key, 4) if account.pix_key else None,
        status=account.status,
        is_primary=account.is_primary,
        verified_at=account.verified_at,
        rejection_reason=account.rejection_reason,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


async def list_family_members(
    db: AsyncSession, user_id: uuid.UUID
) -> list[ParticipantFamilyMember]:
    return list(
        (
            await db.execute(
                select(ParticipantFamilyMember)
                .where(ParticipantFamilyMember.user_id == user_id)
                .order_by(ParticipantFamilyMember.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


async def create_family_member(
    db: AsyncSession,
    user: User,
    payload: FamilyMemberCreate,
    request: Optional[Request] = None,
) -> ParticipantFamilyMember:
    member = ParticipantFamilyMember(
        user_id=user.id,
        full_name=payload.full_name.strip(),
        kinship=payload.kinship,
        birth_date=payload.birth_date,
        phone=payload.phone,
        cpf=payload.cpf,
        cpf_hash=_cpf_hash(payload.cpf),
        is_legal_guardian=payload.is_legal_guardian,
        authorization_reference=payload.authorization_reference,
        notes=payload.notes,
    )
    db.add(member)
    audit_service.record(
        db,
        action="account.family_member_created",
        entity_type="ParticipantFamilyMember",
        actor=user,
        details={"kinship": member.kinship, "is_legal_guardian": member.is_legal_guardian},
        request=request,
    )
    await db.commit()
    await db.refresh(member)
    return member


async def update_family_member(
    db: AsyncSession,
    user: User,
    member_id: uuid.UUID,
    payload: FamilyMemberUpdate,
    request: Optional[Request] = None,
) -> ParticipantFamilyMember:
    member = (
        (
            await db.execute(
                select(ParticipantFamilyMember).where(
                    ParticipantFamilyMember.id == member_id,
                    ParticipantFamilyMember.user_id == user.id,
                )
            )
        )
        .scalars()
        .first()
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Familiar nao encontrado.",
        )
    data = payload.model_dump(exclude_unset=True)
    for field in FAMILY_REQUIRED_FIELDS & set(data):
        if data[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Campo obrigatorio nao pode ser vazio: {field}.",
            )
    for field, value in data.items():
        if field in {"full_name", "kinship"} and value is not None:
            value = value.strip()
        if field == "cpf":
            member.cpf_hash = _cpf_hash(value)
        setattr(member, field, value)
    audit_service.record(
        db,
        action="account.family_member_updated",
        entity_type="ParticipantFamilyMember",
        actor=user,
        entity_id=str(member.id),
        details={"fields": sorted(data.keys())},
        request=request,
    )
    await db.commit()
    await db.refresh(member)
    return member


async def delete_family_member(
    db: AsyncSession,
    user: User,
    member_id: uuid.UUID,
    request: Optional[Request] = None,
) -> None:
    member = (
        (
            await db.execute(
                select(ParticipantFamilyMember).where(
                    ParticipantFamilyMember.id == member_id,
                    ParticipantFamilyMember.user_id == user.id,
                )
            )
        )
        .scalars()
        .first()
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Familiar nao encontrado.",
        )
    await db.delete(member)
    audit_service.record(
        db,
        action="account.family_member_deleted",
        entity_type="ParticipantFamilyMember",
        actor=user,
        entity_id=str(member_id),
        request=request,
    )
    await db.commit()


def family_member_response(member: ParticipantFamilyMember) -> FamilyMemberResponse:
    return FamilyMemberResponse(
        id=member.id,
        full_name=member.full_name,
        kinship=member.kinship,
        birth_date=member.birth_date,
        phone_masked=mask_phone(member.phone) if member.phone else None,
        cpf_masked=mask_cpf(member.cpf) if member.cpf else None,
        is_legal_guardian=member.is_legal_guardian,
        authorization_reference=member.authorization_reference,
        notes=member.notes,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


async def list_journeys(db: AsyncSession, user_id: uuid.UUID) -> list[JourneyEnrollment]:
    result = await db.execute(
        select(JourneyEnrollment)
        .where(JourneyEnrollment.user_id == user_id)
        .order_by(JourneyEnrollment.created_at.asc())
    )
    return list(result.scalars().all())


async def ensure_journey(
    db: AsyncSession,
    user_id: uuid.UUID,
    journey_type: JourneyType,
    *,
    status: JourneyStatus = JourneyStatus.ACTIVE,
    source_invitation_id: Optional[uuid.UUID] = None,
) -> JourneyEnrollment:
    journey = (
        (
            await db.execute(
                select(JourneyEnrollment).where(
                    JourneyEnrollment.user_id == user_id,
                    JourneyEnrollment.journey_type == journey_type,
                )
            )
        )
        .scalars()
        .first()
    )
    if journey:
        journey.status = status
        if status == JourneyStatus.ACTIVE and journey.activated_at is None:
            journey.activated_at = _now()
        if source_invitation_id:
            journey.source_invitation_id = source_invitation_id
        return journey
    journey = JourneyEnrollment(
        user_id=user_id,
        journey_type=journey_type,
        status=status,
        activated_at=_now() if status == JourneyStatus.ACTIVE else None,
        source_invitation_id=source_invitation_id,
    )
    db.add(journey)
    await db.flush()
    return journey


async def set_journey_status(
    db: AsyncSession,
    admin: User,
    target_user_id: uuid.UUID,
    journey_type: JourneyType,
    payload: JourneyStatusUpdate,
    request: Optional[Request] = None,
) -> JourneyEnrollment:
    journey = await ensure_journey(db, target_user_id, journey_type, status=payload.status)
    if payload.status == JourneyStatus.ACTIVE and journey.activated_at is None:
        journey.activated_at = _now()
    if payload.notes:
        journey.notes = payload.notes
    audit_service.record(
        db,
        action="journey.status_updated",
        entity_type="JourneyEnrollment",
        actor=admin,
        entity_id=str(journey.id),
        details={"journey_type": journey_type.value, "status": payload.status.value},
        request=request,
    )
    await db.commit()
    await db.refresh(journey)
    return journey


async def qualification_responses(
    db: AsyncSession, user_id: uuid.UUID
) -> list[QualificationResponse]:
    quals = (
        await db.execute(
            select(ProfessionalQualification).where(ProfessionalQualification.user_id == user_id)
        )
    ).scalars().all()
    return [
        QualificationResponse(
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
        for q in quals
    ]


async def account_response(
    db: AsyncSession, user: User, profile: PersonProfile
) -> AccountResponse:
    journeys = await list_journeys(db, user.id)
    qualifications = await qualification_responses(db, user.id)
    return AccountResponse(
        profile=profile_response(user, profile),
        journeys=[JourneyResponse.model_validate(j) for j in journeys],
        qualifications=qualifications,
    )
