from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.core.deps import get_db, get_current_user_context, require_admin, UserContext
from app.models.network import LocationStatus
from app.schemas.network import LocationCreate, LocationResponse
from app.services import network_service, organization_service

router = APIRouter(prefix="/locations", tags=["Locations"])


class LocationStatusUpdate(BaseModel):
    status: LocationStatus


@router.get("", response_model=List[LocationResponse])
async def list_locations(
    city: Optional[str] = None,
    state: Optional[str] = None,
    status: Optional[LocationStatus] = None,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    org_ids = None
    public_only = False

    if context.is_admin:
        pass
    elif context.is_client:
        # Multi-tenant: cliente só enxerga locais da própria organização.
        org_ids = context.client_organization_ids
    elif context.is_participant:
        # Participante só enxerga a rede já validada.
        public_only = True
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: usuário sem perfil operacional.",
        )

    locs = await network_service.list_locations(
        db,
        city=city,
        state=state,
        status=status,
        organization_ids=org_ids,
        public_only=public_only,
    )
    return [LocationResponse.model_validate(l) for l in locs]


@router.post("", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    loc_in: LocationCreate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Administradores ou gestores de organização cliente podem cadastrar locais.",
        )

    if context.is_admin:
        if loc_in.organization_id:
            org = await organization_service.get_organization_by_id(
                db, str(loc_in.organization_id)
            )
            if not org:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organização informada não existe.",
                )
    else:
        if not context.primary_organization_id or not context.is_manager_of(
            context.primary_organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cliente não possui organização ativa para vincular o local.",
            )
        # Cliente nunca escolhe organização, status nem confiabilidade.
        loc_in.organization_id = context.primary_organization_id
        loc_in.status = LocationStatus.DECLARADO
        loc_in.reliability_score = 100.0

    loc = await network_service.create_location(db, loc_in)
    return LocationResponse.model_validate(loc)


@router.patch("/{location_id}/status", response_model=LocationResponse)
async def update_status(
    location_id: UUID,
    body: LocationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    """ADMIN e CLIENT_ADMIN podem validar/liberar locais da propria organizacao."""
    if not context.is_admin and not context.is_client_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores ou gestores de cliente podem decidir o status do local.",
        )
    loc = await network_service.get_location(db, location_id)
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local não encontrado.")
    if not context.is_admin:
        if not loc.organization_id or not context.is_manager_of(loc.organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado ao local de outra organizacao.",
            )

    allowed = network_service.LOCATION_TRANSITIONS.get(loc.status, set())
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transição inválida de {loc.status.value} para {body.status.value}.",
        )

    loc = await network_service.update_location_status(db, location_id, body.status)
    return LocationResponse.model_validate(loc)


@router.post("/seed", status_code=status.HTTP_200_OK)
async def seed_locations(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    await network_service.seed_default_network(db)
    return {"status": "ok", "message": "Locais de aplicação semeados com sucesso."}
