import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_context, get_db, require_admin, UserContext
from app.models.network import Location
from app.models.participant import (
    Document,
    DocumentOwnerType,
    RepresentativeLinkStatus,
    RepresentativeSchoolLink,
)
from app.schemas.participant import DocumentResponse, DocumentReviewRequest
from app.services import document_service, storage_service
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("/me", response_model=list[DocumentResponse])
async def list_my_documents(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    return await document_service.list_documents(
        db, DocumentOwnerType.PERSON, context.user.id
    )


@router.post("/me", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_my_document(
    request: Request,
    document_type: str = Form(...),
    expires_at: Optional[datetime] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    return await document_service.upload_document(
        db,
        context.user,
        file,
        owner_type=DocumentOwnerType.PERSON,
        owner_id=context.user.id,
        document_type=document_type,
        expires_at=expires_at,
        request=request,
    )


async def _can_access(db: AsyncSession, context: UserContext, doc: Document) -> bool:
    if context.is_admin:
        return True
    if doc.owner_type == DocumentOwnerType.PERSON:
        return doc.owner_id == context.user.id
    if doc.owner_type == DocumentOwnerType.LOCATION:
        if context.is_client:
            return False
        link = (
            (
                await db.execute(
                    select(RepresentativeSchoolLink).where(
                        RepresentativeSchoolLink.representative_user_id == context.user.id,
                        RepresentativeSchoolLink.location_id == doc.owner_id,
                        RepresentativeSchoolLink.status == RepresentativeLinkStatus.ACTIVE,
                    )
                )
            )
            .scalars()
            .first()
        )
        return link is not None
    if doc.owner_type == DocumentOwnerType.REPRESENTATIVE_LINK:
        link = (
            (
                await db.execute(
                    select(RepresentativeSchoolLink).where(
                        RepresentativeSchoolLink.id == doc.owner_id
                    )
                )
            )
            .scalars()
            .first()
        )
        if not link:
            return False
        return link.representative_user_id == context.user.id
    return False


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    doc = await document_service.get_document(db, document_id)
    if not await _can_access(db, context, doc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    try:
        content = await run_in_threadpool(storage_service.read_document, doc.storage_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo nao encontrado."
        )
    return Response(
        content=content,
        media_type=doc.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.file_name)}",
            "Cache-Control": "private, no-store",
        },
    )


@router.patch("/{document_id}/review", response_model=DocumentResponse)
async def review_document(
    document_id: uuid.UUID,
    payload: DocumentReviewRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    return await document_service.review_document(
        db, context.user, document_id, payload, request
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    doc = await document_service.get_document(db, document_id)
    if not context.is_admin and doc.uploaded_by_user_id != context.user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    await document_service.delete_document(db, context.user, document_id, request)
