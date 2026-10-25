from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel

from app.core.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.organization import OrganizationStatus
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.services import organization_service

router = APIRouter(prefix="/organizations", tags=["Organizations"])

class StatusUpdateRequest(BaseModel):
    status: OrganizationStatus

@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    org_in: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org = await organization_service.create_organization(db, name=org_in.name, cnpj=org_in.cnpj)
    return OrganizationResponse.model_validate(org)

@router.get("", response_model=List[OrganizationResponse])
async def list_orgs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    orgs = await organization_service.get_organizations(db, skip=skip, limit=limit)
    return [OrganizationResponse.model_validate(o) for o in orgs]

@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_org(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org = await organization_service.get_organization_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizadora não encontrada.")
    return OrganizationResponse.model_validate(org)

@router.patch("/{org_id}/status", response_model=OrganizationResponse)
async def update_status(
    org_id: str,
    body: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org = await organization_service.update_organization_status(db, org_id, body.status)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizadora não encontrada.")
    return OrganizationResponse.model_validate(org)
