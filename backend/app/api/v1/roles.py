from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.core.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.role import Role
from app.schemas.role import RoleCreate, RoleResponse

router = APIRouter(prefix="/roles", tags=["Roles"])

@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_in: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    existing = await db.execute(select(Role).where(Role.name == role_in.name))
    if existing.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role já existe.")
    role = Role(name=role_in.name, description=role_in.description, is_system=role_in.is_system)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return RoleResponse.model_validate(role)

@router.get("", response_model=List[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(select(Role))
    return [RoleResponse.model_validate(r) for r in result.scalars().all()]
