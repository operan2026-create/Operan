import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_context, get_db, require_admin, UserContext
from app.models.participant import (
    JourneyType,
    ParticipantConsent,
)
from app.models.user import User
from app.schemas.participant import (
    AccountResponse,
    AvatarUpdate,
    BankAccountCreate,
    BankAccountResponse,
    BankAccountUpdate,
    ConsentCreate,
    ConsentResponse,
    FamilyMemberCreate,
    FamilyMemberResponse,
    FamilyMemberUpdate,
    JourneyResponse,
    JourneyStatusUpdate,
    PersonProfileResponse,
    PersonProfileUpdate,
)
from app.services import account_service, audit_service

router = APIRouter(prefix="/account", tags=["Account"])


async def _profile_or_404(db: AsyncSession, context: UserContext):
    profile = context.person_profile or await account_service.get_profile(db, context.user.id)
    if not profile:
        profile = await account_service.ensure_profile_from_legacy(
            db, context.user, context.professional
        )
        if profile:
            await db.commit()
            await db.refresh(profile)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil global ainda nao cadastrado para esta conta.",
        )
    return profile


@router.get("/me", response_model=AccountResponse)
async def get_account(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    profile = await _profile_or_404(db, context)
    return await account_service.account_response(db, context.user, profile)


@router.get("/profile", response_model=PersonProfileResponse)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    profile = await _profile_or_404(db, context)
    return account_service.profile_response(context.user, profile)


@router.patch("/profile", response_model=PersonProfileResponse)
async def update_profile(
    payload: PersonProfileUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    profile = await _profile_or_404(db, context)
    return await account_service.update_profile(
        db, context.user, profile, payload, request
    )


@router.get("/avatar")
async def get_my_avatar(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    profile = await _profile_or_404(db, context)
    content = account_service.avatar_bytes(profile)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Foto de perfil nao encontrada."
        )
    return Response(
        content=content,
        media_type=profile.avatar_mime_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post("/avatar", response_model=PersonProfileResponse)
async def update_my_avatar(
    payload: AvatarUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    profile = await _profile_or_404(db, context)
    return await account_service.update_avatar(
        db, context.user, profile, payload, request
    )


@router.get("/bank-accounts", response_model=List[BankAccountResponse])
async def list_my_bank_accounts(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    accounts = await account_service.list_bank_accounts(db, context.user.id)
    return [account_service.bank_account_response(account) for account in accounts]


@router.post(
    "/bank-accounts",
    response_model=BankAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_bank_account(
    payload: BankAccountCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    account = await account_service.create_bank_account(
        db, context.user, payload, request
    )
    return account_service.bank_account_response(account)


@router.patch("/bank-accounts/{account_id}", response_model=BankAccountResponse)
async def update_my_bank_account(
    account_id: uuid.UUID,
    payload: BankAccountUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    account = await account_service.update_bank_account(
        db, context.user, account_id, payload, request
    )
    return account_service.bank_account_response(account)


@router.delete("/bank-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_bank_account(
    account_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    await account_service.delete_bank_account(db, context.user, account_id, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/family-members", response_model=List[FamilyMemberResponse])
async def list_my_family_members(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    members = await account_service.list_family_members(db, context.user.id)
    return [account_service.family_member_response(member) for member in members]


@router.post(
    "/family-members",
    response_model=FamilyMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_family_member(
    payload: FamilyMemberCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    member = await account_service.create_family_member(
        db, context.user, payload, request
    )
    return account_service.family_member_response(member)


@router.patch("/family-members/{member_id}", response_model=FamilyMemberResponse)
async def update_my_family_member(
    member_id: uuid.UUID,
    payload: FamilyMemberUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    member = await account_service.update_family_member(
        db, context.user, member_id, payload, request
    )
    return account_service.family_member_response(member)


@router.delete("/family-members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_family_member(
    member_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    await account_service.delete_family_member(db, context.user, member_id, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/journeys", response_model=List[JourneyResponse])
async def list_my_journeys(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    journeys = await account_service.list_journeys(db, context.user.id)
    return [JourneyResponse.model_validate(journey) for journey in journeys]


@router.patch(
    "/users/{user_id}/journeys/{journey_type}",
    response_model=JourneyResponse,
)
async def set_user_journey_status(
    user_id: uuid.UUID,
    journey_type: JourneyType,
    payload: JourneyStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    target = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")
    journey = await account_service.set_journey_status(
        db, context.user, user_id, journey_type, payload, request
    )
    return JourneyResponse.model_validate(journey)


@router.get("/consents", response_model=List[ConsentResponse])
async def list_consents(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    consents = (
        await db.execute(
            select(ParticipantConsent)
            .where(ParticipantConsent.user_id == context.user.id)
            .order_by(ParticipantConsent.granted_at.desc())
        )
    ).scalars().all()
    return [ConsentResponse.model_validate(consent, from_attributes=True) for consent in consents]


@router.post("/consents", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def grant_consent(
    payload: ConsentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    existing = (
        (
            await db.execute(
                select(ParticipantConsent).where(
                    ParticipantConsent.user_id == context.user.id,
                    ParticipantConsent.consent_type == payload.consent_type,
                    ParticipantConsent.policy_version == payload.policy_version,
                    ParticipantConsent.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .first()
    )
    if existing:
        return ConsentResponse.model_validate(existing, from_attributes=True)
    ip_address, user_agent = audit_service.request_metadata(request)
    consent = ParticipantConsent(
        user_id=context.user.id,
        consent_type=payload.consent_type,
        policy_version=payload.policy_version,
        purpose=payload.purpose,
        legal_basis=payload.legal_basis,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(consent)
    audit_service.record(
        db,
        action="consent.granted",
        entity_type="ParticipantConsent",
        actor=context.user,
        details={
            "consent_type": payload.consent_type,
            "policy_version": payload.policy_version,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(consent)
    return ConsentResponse.model_validate(consent, from_attributes=True)


@router.patch("/consents/{consent_id}/revoke", response_model=ConsentResponse)
async def revoke_consent(
    consent_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    consent = (
        (await db.execute(select(ParticipantConsent).where(ParticipantConsent.id == consent_id)))
        .scalars()
        .first()
    )
    if not consent or consent.user_id != context.user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Consentimento nao encontrado."
        )
    if consent.revoked_at is None:
        from datetime import datetime, timezone

        consent.revoked_at = datetime.now(timezone.utc)
        audit_service.record(
            db,
            action="consent.revoked",
            entity_type="ParticipantConsent",
            actor=context.user,
            entity_id=str(consent.id),
            request=request,
        )
        await db.commit()
        await db.refresh(consent)
    return ConsentResponse.model_validate(consent, from_attributes=True)
