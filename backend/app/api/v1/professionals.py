from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.deps import get_db, get_current_user_context, require_admin, UserContext
from app.schemas.network import ProfessionalCreate, ProfessionalResponse
from app.services import network_service

router = APIRouter(prefix="/professionals", tags=["Professionals"])

@router.get("", response_model=List[ProfessionalResponse])
async def list_professionals(
    city: Optional[str] = None,
    state: Optional[str] = None,
    function: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: a visualizacao da rede de profissionais e restrita a administracao e contratantes autorizados.",
        )

    organization_ids = None
    if not context.is_admin:
        organization_ids = context.client_organization_ids
        if not organization_ids:
            return []
    profs = await network_service.list_professionals(
        db,
        city=city,
        state=state,
        organization_ids=organization_ids,
        function_name=function,
    )
    qualifications = await network_service.qualifications_for_users(
        db, [p.user_id for p in profs]
    )
    output = []
    for professional in profs:
        response = ProfessionalResponse.model_validate(professional)
        response.public_id = professional.user.public_id if professional.user else None
        response.qualifications = qualifications.get(professional.user_id, [])
        output.append(response)
    return output

@router.post("", response_model=ProfessionalResponse, status_code=status.HTTP_201_CREATED)
async def create_professional(
    prof_in: ProfessionalCreate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    prof = await network_service.create_professional(db, prof_in)
    return ProfessionalResponse.model_validate(prof)

