from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.core.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.network import LocationStatus
from app.schemas.network import LocationCreate, LocationResponse
from app.services import network_service

router = APIRouter(prefix="/locations", tags=["Locations"])

class LocationStatusUpdate(BaseModel):
    status: LocationStatus

@router.get("", response_model=List[LocationResponse])
async def list_locations(
    city: Optional[str] = None,
    state: Optional[str] = None,
    status: Optional[LocationStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    locs = await network_service.list_locations(db, city=city, state=state, status=status)
    return [LocationResponse.model_validate(l) for l in locs]

@router.post("", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    loc_in: LocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    loc = await network_service.create_location(db, loc_in)
    return LocationResponse.model_validate(loc)

@router.patch("/{location_id}/status", response_model=LocationResponse)
async def update_status(
    location_id: UUID,
    body: LocationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    loc = await network_service.update_location_status(db, location_id, body.status)
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local não encontrado.")
    return LocationResponse.model_validate(loc)

@router.post("/seed", status_code=status.HTTP_200_OK)
async def seed_locations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await network_service.seed_default_network(db)
    return {"status": "ok", "message": "Locais de aplicação semeados com sucesso."}
