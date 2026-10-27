from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_current_user_context,
    get_db,
    get_optional_current_user,
    UserContext,
)
from app.models.network import Location
from app.models.organization import Organization
from app.models.user import User
from app.schemas.participant import (
    InvitationAcceptRequest,
    InvitationCreate,
    InvitationCreatedResponse,
    InvitationResponse,
    InvitationValidationResponse,
    PublicInvitationCreate,
    PublicInvitationCreatedResponse,
    PublicInvitationResponse,
    PublicInvitationValidationResponse,
    RegistrationDraftResponse,
    RegistrationDraftUpsert,
)
from app.schemas.user import UserResponse
from app.security.encryption import crypto_manager
from app.security.jwt import create_access_token
from app.services import invitation_service, registration_draft_service

router = APIRouter(prefix="/invitations", tags=["Invitations"])


class InvitationAcceptedResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


async def _names(db: AsyncSession, invitation) -> tuple[Optional[str], Optional[str]]:
    org_name = None
    location_name = None
    if invitation.organization_id:
        org = (
            await db.execute(select(Organization).where(Organization.id == invitation.organization_id))
        ).scalars().first()
        org_name = org.name if org else None
    if invitation.location_id:
        location = (
            await db.execute(select(Location).where(Location.id == invitation.location_id))
        ).scalars().first()
        location_name = location.name if location else None
    return org_name, location_name


def _accept_path(invitation) -> Optional[str]:
    if (
        invitation.status.value == "PENDING"
        and getattr(invitation, "token_encrypted", None)
    ):
        return f"/convite/{crypto_manager.decrypt_data(invitation.token_encrypted)}"
    return None


def _public_accept_path(invitation, effective_status=None) -> Optional[str]:
    status = effective_status or invitation_service.public_effective_status(invitation)
    if status.value == "ACTIVE" and getattr(invitation, "token_encrypted", None):
        return f"/convite-publico/{crypto_manager.decrypt_data(invitation.token_encrypted)}"
    return None


def _public_response(invitation) -> PublicInvitationResponse:
    effective_status = invitation_service.public_effective_status(invitation)
    return PublicInvitationResponse(
        id=invitation.id,
        label=invitation.label,
        journey_type=invitation.journey_type,
        purpose=invitation.purpose,
        mission_id=invitation.mission_id,
        required_data_categories=invitation.required_data_categories or [],
        organization_id=invitation.organization_id,
        organization_name=invitation.organization.name if invitation.organization else None,
        location_id=invitation.location_id,
        location_name=invitation.location.name if invitation.location else None,
        status=effective_status,
        expires_at=invitation.expires_at,
        max_uses=invitation.max_uses,
        uses_count=invitation.uses_count,
        accept_path=_public_accept_path(invitation, effective_status),
        revoked_at=invitation.revoked_at,
        created_at=invitation.created_at,
    )


def _response(invitation, org_name=None, location_name=None) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        email=crypto_manager.decrypt_data(invitation.email_encrypted),
        journey_type=invitation.journey_type,
        purpose=invitation.purpose,
        mission_id=invitation.mission_id,
        required_data_categories=invitation.required_data_categories or [],
        organization_id=invitation.organization_id,
        organization_name=org_name,
        location_id=invitation.location_id,
        location_name=location_name,
        status=invitation.status,
        token_prefix=invitation.token_prefix,
        accept_path=_accept_path(invitation),
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        revoked_at=invitation.revoked_at,
        created_at=invitation.created_at,
    )


@router.post("", response_model=InvitationCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    payload: InvitationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores ou gestores de cliente podem criar convites.",
        )
    invitation, token = await invitation_service.create_invitation(
        db,
        email=str(payload.email),
        journey_type=payload.journey_type,
        organization_id=payload.organization_id,
        location_id=payload.location_id,
        creator=context,
        expires_in_days=payload.expires_in_days,
        purpose=payload.purpose,
        mission_id=payload.mission_id,
        required_data_categories=payload.required_data_categories,
        request=request,
    )
    org_name, location_name = await _names(db, invitation)
    return InvitationCreatedResponse(
        id=invitation.id,
        email=crypto_manager.decrypt_data(invitation.email_encrypted),
        journey_type=invitation.journey_type,
        purpose=invitation.purpose,
        mission_id=invitation.mission_id,
        required_data_categories=invitation.required_data_categories or [],
        organization_id=invitation.organization_id,
        organization_name=org_name,
        location_id=invitation.location_id,
        location_name=location_name,
        status=invitation.status,
        expires_at=invitation.expires_at,
        token=token,
        accept_path=f"/convite/{token}",
    )


@router.get("", response_model=List[InvitationResponse])
async def list_invitations(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    invitations = await invitation_service.list_invitations(db, context)
    output = []
    for invitation in invitations:
        output.append(
            _response(
                invitation,
                invitation.organization.name if invitation.organization else None,
                invitation.location.name if invitation.location else None,
            )
        )
    return output


@router.post("/{invitation_id}/revoke", response_model=InvitationResponse)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    invitation = await invitation_service.revoke_invitation(
        db, invitation_id, context, request
    )
    return _response(
        invitation,
        invitation.organization.name if invitation.organization else None,
        invitation.location.name if invitation.location else None,
    )


@router.post(
    "/{invitation_id}/regenerate",
    response_model=InvitationCreatedResponse,
)
async def regenerate_invitation_link(
    invitation_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    invitation, token = await invitation_service.regenerate_token(
        db, invitation_id, context, request
    )
    org_name, location_name = await _names(db, invitation)
    return InvitationCreatedResponse(
        id=invitation.id,
        email=crypto_manager.decrypt_data(invitation.email_encrypted),
        journey_type=invitation.journey_type,
        purpose=invitation.purpose,
        mission_id=invitation.mission_id,
        required_data_categories=invitation.required_data_categories or [],
        organization_id=invitation.organization_id,
        organization_name=org_name,
        location_id=invitation.location_id,
        location_name=location_name,
        status=invitation.status,
        expires_at=invitation.expires_at,
        token=token,
        accept_path=f"/convite/{token}",
    )


@router.post(
    "/public",
    response_model=PublicInvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_public_invitation(
    payload: PublicInvitationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores ou gestores de cliente podem criar links publicos.",
        )
    invitation, token = await invitation_service.create_public_invitation(
        db,
        journey_type=payload.journey_type,
        organization_id=payload.organization_id,
        location_id=payload.location_id,
        label=payload.label,
        creator=context,
        expires_in_days=payload.expires_in_days,
        max_uses=payload.max_uses,
        purpose=payload.purpose,
        mission_id=payload.mission_id,
        required_data_categories=payload.required_data_categories,
        request=request,
    )
    return PublicInvitationCreatedResponse(
        id=invitation.id,
        label=invitation.label,
        journey_type=invitation.journey_type,
        purpose=invitation.purpose,
        mission_id=invitation.mission_id,
        required_data_categories=invitation.required_data_categories or [],
        organization_id=invitation.organization_id,
        organization_name=invitation.organization.name if invitation.organization else None,
        location_id=invitation.location_id,
        location_name=invitation.location.name if invitation.location else None,
        status=invitation.status,
        expires_at=invitation.expires_at,
        max_uses=invitation.max_uses,
        uses_count=invitation.uses_count,
        token=token,
        accept_path=f"/convite-publico/{token}",
    )


@router.get("/public", response_model=List[PublicInvitationResponse])
async def list_public_invitations(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    invitations = await invitation_service.list_public_invitations(db, context)
    return [_public_response(invitation) for invitation in invitations]


@router.post(
    "/public/{invitation_id}/revoke", response_model=PublicInvitationResponse
)
async def revoke_public_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    invitation = await invitation_service.revoke_public_invitation(
        db, invitation_id, context, request
    )
    return _public_response(invitation)


@router.get(
    "/public/validate/{token}", response_model=PublicInvitationValidationResponse
)
async def validate_public_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    data = await invitation_service.validate_public_invitation(
        db, token, current_user
    )
    return PublicInvitationValidationResponse(**data)


@router.post(
    "/public/{token}/accept",
    response_model=InvitationAcceptedResponse,
)
async def accept_public_invitation(
    token: str,
    payload: InvitationAcceptRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    user, _profile = await invitation_service.accept_public_invitation(
        db,
        token=token,
        payload=payload,
        current_user=current_user,
        request=request,
    )
    context = await get_current_user_context(current_user=user, db=db)
    user_response = context.to_user_response()
    jwt = create_access_token(
        data={"sub": user.public_id, "role": context.primary_role}
    )
    return InvitationAcceptedResponse(
        access_token=jwt,
        user=UserResponse.model_validate(user_response),
    )


@router.get("/public/{token}/draft", response_model=RegistrationDraftResponse)
async def get_public_registration_draft(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    return await registration_draft_service.get_draft(db, token, public=True)


@router.put("/public/{token}/draft", response_model=RegistrationDraftResponse)
async def save_public_registration_draft(
    token: str,
    payload: RegistrationDraftUpsert,
    db: AsyncSession = Depends(get_db),
):
    return await registration_draft_service.save_draft(
        db,
        token,
        public=True,
        current_step=payload.current_step,
        data=payload.data,
    )


@router.get("/{token}/draft", response_model=RegistrationDraftResponse)
async def get_registration_draft(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    return await registration_draft_service.get_draft(db, token, public=False)


@router.put("/{token}/draft", response_model=RegistrationDraftResponse)
async def save_registration_draft(
    token: str,
    payload: RegistrationDraftUpsert,
    db: AsyncSession = Depends(get_db),
):
    return await registration_draft_service.save_draft(
        db,
        token,
        public=False,
        current_step=payload.current_step,
        data=payload.data,
    )


@router.get("/validate/{token}", response_model=InvitationValidationResponse)
async def validate_invitation(token: str, db: AsyncSession = Depends(get_db)):
    data = await invitation_service.validate_invitation(db, token)
    return InvitationValidationResponse(**data)


@router.post("/{token}/accept", response_model=InvitationAcceptedResponse)
async def accept_invitation(
    token: str,
    payload: InvitationAcceptRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    user, _profile = await invitation_service.accept_invitation(
        db,
        token=token,
        payload=payload,
        current_user=current_user,
        request=request,
    )
    context = await get_current_user_context(current_user=user, db=db)
    user_response = context.to_user_response()
    jwt = create_access_token(
        data={"sub": user.public_id, "role": context.primary_role}
    )
    return InvitationAcceptedResponse(
        access_token=jwt,
        user=UserResponse.model_validate(user_response),
    )
