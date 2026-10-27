from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.deps import get_db, require_admin, UserContext
from app.models.membership import Membership, MembershipStatus
from app.models.role import Role
from app.models.user import User, UserStatus
from app.schemas.user import UserAdminResponse, UserStatusUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=List[UserAdminResponse])
async def list_users(
    status_filter: Optional[UserStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    query = select(User).order_by(User.created_at.desc())
    if status_filter:
        query = query.where(User.status == status_filter)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return [UserAdminResponse.model_validate(u) for u in result.scalars().all()]


@router.patch("/{user_id}/status", response_model=UserAdminResponse)
async def update_user_status(
    user_id: UUID,
    body: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    # Admins cannot change their own status (avoids accidental lockout).
    if user_id == context.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administradores não podem alterar o próprio status.",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    # Never allow the last active admin to be blocked/deactivated.
    if body.status != UserStatus.ACTIVE:
        admin_count = await db.execute(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .join(Role, Membership.role_id == Role.id)
            .where(
                Role.name == "ADMIN",
                Membership.status == MembershipStatus.ACTIVE,
                User.status == UserStatus.ACTIVE,
                User.id != user_id,
            )
        )
        if admin_count.scalars().first() is None:
            is_admin_target = await db.execute(
                select(Membership)
                .join(Role, Membership.role_id == Role.id)
                .where(
                    Membership.user_id == user_id,
                    Membership.status == MembershipStatus.ACTIVE,
                    Role.name == "ADMIN",
                )
            )
            if is_admin_target.scalars().first() is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Não é possível desativar o último administrador ativo.",
                )

    user.status = body.status
    await db.commit()
    await db.refresh(user)
    return UserAdminResponse.model_validate(user)
