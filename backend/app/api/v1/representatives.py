import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_current_user_context,
    get_db,
    require_admin,
    require_representative,
    UserContext,
)
from app.models.participant import DocumentOwnerType, WorkflowStage
from app.schemas.participant import (
    RepresentativeLinkResponse,
    RepresentativeLinkUpdate,
    WorkflowDecisionRequest,
    WorkflowEventCreate,
    WorkflowEventResponse,
)
from app.services import document_service, representative_service

router = APIRouter(prefix="/representatives", tags=["Representatives"])


@router.get("/schools", response_model=list[RepresentativeLinkResponse])
async def list_my_schools(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_representative),
):
    return await representative_service.list_schools_for_representative(db, context.user.id)


@router.get("/schools/{location_id}")
async def get_my_school(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_representative),
):
    link = await representative_service.get_link_for_user(db, context.user.id, location_id)
    events = await representative_service.list_workflow_events(db, context, location_id)
    documents = await document_service.list_documents(
        db, DocumentOwnerType.LOCATION, location_id
    )
    return {
        "link": representative_service._link_response(link),
        "events": events,
        "documents": documents,
    }


@router.post("/schools/{location_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_school_document(
    location_id: uuid.UUID,
    request: Request,
    document_type: str = Form(...),
    expires_at: Optional[datetime] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_representative),
):
    await representative_service.get_link_for_user(db, context.user.id, location_id)
    return await document_service.upload_document(
        db,
        context.user,
        file,
        owner_type=DocumentOwnerType.LOCATION,
        owner_id=location_id,
        document_type=document_type,
        expires_at=expires_at,
        request=request,
    )


@router.get("/schools/{location_id}/documents")
async def list_school_documents(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_representative),
):
    await representative_service.get_link_for_user(db, context.user.id, location_id)
    return await document_service.list_documents(db, DocumentOwnerType.LOCATION, location_id)


@router.get("/schools/{location_id}/events", response_model=list[WorkflowEventResponse])
async def list_school_events(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    return await representative_service.list_workflow_events(db, context, location_id)


@router.post(
    "/schools/{location_id}/submit/{stage}",
    response_model=WorkflowEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_school_stage(
    location_id: uuid.UUID,
    stage: WorkflowStage,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_representative),
):
    return await representative_service.submit_stage(
        db, context.user, location_id, stage, request
    )


@router.get(
    "/locations/{location_id}/links", response_model=list[RepresentativeLinkResponse]
)
async def list_location_representatives(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    return await representative_service.list_representatives_for_school(
        db, context, location_id
    )


@router.patch("/links/{link_id}", response_model=RepresentativeLinkResponse)
async def update_representative_link(
    link_id: uuid.UUID,
    payload: RepresentativeLinkUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client_manager:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    return await representative_service.update_link(
        db, context, link_id, payload, request
    )


@router.post(
    "/locations/{location_id}/stages/{stage}/decision",
    response_model=WorkflowEventResponse,
)
async def decide_location_stage(
    location_id: uuid.UUID,
    stage: WorkflowStage,
    payload: WorkflowDecisionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client_manager:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    return await representative_service.decide_stage(
        db, context, location_id, stage, payload, request
    )


@router.post(
    "/schools/{location_id}/request/{stage}", response_model=WorkflowEventResponse
)
async def request_school_stage_alias(
    location_id: uuid.UUID,
    stage: WorkflowStage,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_representative),
):
    return await representative_service.submit_stage(
        db, context.user, location_id, stage, request
    )

@router.post(
    "/locations/{location_id}/stages/{stage}/submit",
    response_model=WorkflowEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_location_stage_for_staff(
    location_id: uuid.UUID,
    stage: WorkflowStage,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    if not context.is_admin and not context.is_client_manager:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    return await representative_service.submit_stage_for_staff(
        db, context, location_id, stage, request
    )
