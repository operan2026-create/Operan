from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.deps import get_db, get_current_active_user
from app.models.user import User
from app.schemas.network import ProfessionalCreate, ProfessionalResponse
from app.services import network_service

router = APIRouter(prefix="/professionals", tags=["Professionals"])

@router.get("", response_model=List[ProfessionalResponse])
async def list_professionals(
    city: Optional[str] = None,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    profs = await network_service.list_professionals(db, city=city, state=state)
    return [ProfessionalResponse.model_validate(p) for p in profs]

@router.post("", response_model=ProfessionalResponse, status_code=status.HTTP_201_CREATED)
async def create_professional(
    prof_in: ProfessionalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    prof = await network_service.create_professional(db, prof_in)
    return ProfessionalResponse.model_validate(prof)
