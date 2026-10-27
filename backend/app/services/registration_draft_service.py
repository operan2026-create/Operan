import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.participant import (
    InvitationStatus,
    PublicInvitationStatus,
    RegistrationDraft,
    RegistrationDraftStatus,
)
from app.services import invitation_service

MAX_DRAFT_BYTES = 200_000
DRAFT_TTL = timedelta(days=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _expired(draft: RegistrationDraft) -> bool:
    expires_at = _aware(draft.expires_at)
    return expires_at is not None and expires_at <= _now()


async def _active_invitation(
    db: AsyncSession, token: str, *, public: bool
):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Convite invalido ou inexistente.",
        )
    if public:
        invitation = await invitation_service.get_public_by_token(db, token)
        if invitation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Link publico invalido ou inexistente.",
            )
        effective_status = invitation_service.public_effective_status(invitation)
        if effective_status != PublicInvitationStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Este link publico nao esta mais disponivel.",
            )
        return invitation, invitation.expires_at

    invitation = await invitation_service.get_by_token(db, token)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Convite invalido ou inexistente.",
        )
    if (
        invitation.status != InvitationStatus.PENDING
        or invitation_service._is_expired(invitation)
    ):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Este convite nao esta mais disponivel.",
        )
    return invitation, invitation.expires_at


async def _find_draft(
    db: AsyncSession, token: str
) -> Optional[RegistrationDraft]:
    return (
        (
            await db.execute(
                select(RegistrationDraft).where(
                    RegistrationDraft.token_hash == invitation_service.hash_token(token)
                )
            )
        )
        .scalars()
        .first()
    )


def _serialize(draft: RegistrationDraft) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if draft.data_encrypted:
        try:
            parsed = json.loads(draft.data_encrypted)
            if isinstance(parsed, dict):
                data = parsed
        except (TypeError, ValueError):
            data = {}
    return {
        "status": draft.status,
        "current_step": draft.current_step,
        "data": data,
        "expires_at": draft.expires_at,
        "updated_at": draft.updated_at,
    }


def _ensure_editable(draft: RegistrationDraft) -> None:
    if draft.status == RegistrationDraftStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este rascunho ja foi enviado.",
        )
    if draft.status == RegistrationDraftStatus.EXPIRED or _expired(draft):
        draft.status = RegistrationDraftStatus.EXPIRED
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Este rascunho expirou.",
        )


async def get_draft(
    db: AsyncSession, token: str, *, public: bool
) -> dict[str, Any]:
    await _active_invitation(db, token, public=public)
    draft = await _find_draft(db, token)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum rascunho salvo para este convite.",
        )
    if draft.status == RegistrationDraftStatus.IN_PROGRESS and _expired(draft):
        draft.status = RegistrationDraftStatus.EXPIRED
        await db.commit()
        await db.refresh(draft)
    return _serialize(draft)


async def save_draft(
    db: AsyncSession,
    token: str,
    *,
    public: bool,
    current_step: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    invitation, invitation_expires_at = await _active_invitation(
        db, token, public=public
    )
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Os dados do rascunho devem ser um objeto.",
        )
    encoded = json.dumps(data, ensure_ascii=False, default=str)
    if len(encoded.encode("utf-8")) > MAX_DRAFT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Rascunho excede o tamanho maximo permitido.",
        )
    now = _now()
    invitation_expires_at = _aware(invitation_expires_at)
    expires_at = now + DRAFT_TTL
    if invitation_expires_at is not None and invitation_expires_at < expires_at:
        expires_at = invitation_expires_at

    draft = await _find_draft(db, token)
    if draft is None:
        draft = RegistrationDraft(
            id=uuid.uuid4(),
            token_hash=invitation_service.hash_token(token),
            token_prefix=token[:8],
            invitation_id=getattr(invitation, "id", None) if not public else None,
            public_invitation_id=getattr(invitation, "id", None) if public else None,
            user_id=None,
            data_encrypted=encoded,
            current_step=current_step,
            status=RegistrationDraftStatus.IN_PROGRESS,
            expires_at=expires_at,
        )
        db.add(draft)
    else:
        _ensure_editable(draft)
        draft.data_encrypted = encoded
        draft.current_step = current_step
        draft.expires_at = expires_at
        draft.status = RegistrationDraftStatus.IN_PROGRESS

    await db.commit()
    await db.refresh(draft)
    return _serialize(draft)
