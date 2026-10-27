from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, require_admin, UserContext
from app.models.participant import AuditLog
from app.schemas.participant import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    query = (
        select(AuditLog)
        .options(selectinload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    rows = (await db.execute(query)).scalars().all()
    return [
        AuditLogResponse(
            id=row.id,
            actor_public_id=row.actor.public_id if row.actor else None,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            organization_id=row.organization_id,
            details=row.details,
            created_at=row.created_at,
        )
        for row in rows
    ]
