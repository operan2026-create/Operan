import uuid
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.participant import AuditLog

SENSITIVE_KEYS = {
    "cpf",
    "cpf_encrypted",
    "rg",
    "rg_encrypted",
    "phone",
    "phone_encrypted",
    "account",
    "account_encrypted",
    "account_number",
    "account_number_encrypted",
    "holder_cpf",
    "holder_cpf_encrypted",
    "branch",
    "branch_encrypted",
    "pix_key",
    "pix_key_encrypted",
    "password",
    "token",
    "token_hash",
    "email",
    "email_encrypted",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def request_metadata(request: Optional[Request]) -> tuple[Optional[str], Optional[str]]:
    if request is None:
        return None, None
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent[:500] if user_agent else None


def record(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    actor=None,
    entity_id: Optional[str] = None,
    organization_id: Optional[uuid.UUID] = None,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    ip_address, user_agent = request_metadata(request)
    entry = AuditLog(
        actor_user_id=getattr(actor, "id", None),
        actor_public_id=getattr(actor, "public_id", None),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        organization_id=organization_id,
        details=_redact(details) if details else None,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    return entry
