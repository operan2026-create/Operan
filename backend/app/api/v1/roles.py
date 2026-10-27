from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.core.deps import get_db, require_admin, UserContext
from app.models.role import Role
from app.schemas.role import RoleCreate, RoleResponse

router = APIRouter(prefix="/roles", tags=["Roles"])

@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_in: RoleCreate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    name = role_in.name.strip().upper()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome de papel inválido.")
    existing = await db.execute(select(Role).where(Role.name == name))
    if existing.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role já existe.")
    # is_system is a reserved marker; it must never come from API input.
    role = Role(name=name, description=role_in.description, is_system=False)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return RoleResponse.model_validate(role)

@router.get("", response_model=List[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    result = await db.execute(select(Role))
    return [RoleResponse.model_validate(r) for r in result.scalars().all()]

