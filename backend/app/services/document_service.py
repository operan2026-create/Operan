import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.models.participant import (
    Document,
    DocumentOwnerType,
    DocumentStatus,
)
from app.models.user import User
from app.schemas.participant import DocumentResponse, DocumentReviewRequest
from app.services import audit_service, storage_service

DOCUMENT_TYPES = {
    "RG",
    "CNH",
    "CPF",
    "PROOF_OF_ADDRESS",
    "SCHOOL_DOCUMENT",
    "INSPECTION_REPORT",
    "EDUCATION",
    "HEALTH",
    "CRIMINAL_RECORD",
    "OTHER",
}
ALLOWED_DOCUMENTS = {
    "application/pdf": ("pdf", (b"%PDF-",)),
    "image/jpeg": ("jpg", (b"\xff\xd8\xff",)),
    "image/png": ("png", (b"\x89PNG\r\n\x1a\n",)),
}


def _response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        owner_type=doc.owner_type,
        owner_id=doc.owner_id,
        document_type=doc.document_type,
        file_name=doc.file_name,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        sha256=doc.sha256,
        status=doc.status,
        rejection_reason=doc.rejection_reason,
        expires_at=doc.expires_at,
        reviewed_at=doc.reviewed_at,
        created_at=doc.created_at,
        download_path=f"/api/v1/documents/{doc.id}/download",
    )


async def upload_document(
    db: AsyncSession,
    actor: User,
    upload: UploadFile,
    *,
    owner_type: DocumentOwnerType,
    owner_id: uuid.UUID,
    document_type: str,
    expires_at: Optional[datetime],
    request: Optional[Request] = None,
) -> DocumentResponse:
    document_type = document_type.upper()
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tipo de documento invalido."
        )
    content = await upload.read(settings.MAX_DOCUMENT_SIZE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Arquivo vazio.")
    if len(content) > settings.MAX_DOCUMENT_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo excede o limite de 10 MB.",
        )
    mime = (upload.content_type or "").lower()
    if mime not in ALLOWED_DOCUMENTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Formato permitido: PDF, JPEG ou PNG.",
        )
    extension, signatures = ALLOWED_DOCUMENTS[mime]
    if not any(content.startswith(signature) for signature in signatures):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Conteudo do arquivo nao corresponde ao formato declarado.",
        )

    original_name = Path(upload.filename or f"documento.{extension}").name[:255]
    storage_key, digest = await run_in_threadpool(
        storage_service.save_document, owner_id, content, extension
    )
    doc = Document(
        owner_type=owner_type,
        owner_id=owner_id,
        document_type=document_type,
        file_name=original_name,
        storage_key=storage_key,
        mime_type=mime,
        size_bytes=len(content),
        sha256=digest,
        status=DocumentStatus.PENDING,
        uploaded_by_user_id=actor.id,
        expires_at=expires_at,
    )
    db.add(doc)
    await db.flush()
    audit_service.record(
        db,
        action="document.uploaded",
        entity_type="Document",
        actor=actor,
        entity_id=str(doc.id),
        details={
            "owner_type": owner_type.value,
            "owner_id": str(owner_id),
            "document_type": document_type,
            "size_bytes": len(content),
        },
        request=request,
    )
    try:
        await db.commit()
    except Exception:
        await run_in_threadpool(storage_service.delete_document, storage_key)
        raise
    await db.refresh(doc)
    return _response(doc)


async def list_documents(
    db: AsyncSession, owner_type: DocumentOwnerType, owner_id: uuid.UUID
) -> list[DocumentResponse]:
    docs = (
        await db.execute(
            select(Document)
            .where(Document.owner_type == owner_type, Document.owner_id == owner_id)
            .order_by(Document.created_at.desc())
        )
    ).scalars().all()
    return [_response(doc) for doc in docs]


async def get_document(db: AsyncSession, document_id: uuid.UUID) -> Document:
    doc = (
        (await db.execute(select(Document).where(Document.id == document_id))).scalars().first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento nao encontrado.")
    return doc


async def review_document(
    db: AsyncSession,
    admin: User,
    document_id: uuid.UUID,
    payload: DocumentReviewRequest,
    request: Optional[Request] = None,
) -> DocumentResponse:
    doc = await get_document(db, document_id)
    if payload.status == DocumentStatus.REJECTED and not payload.rejection_reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe o motivo da rejeicao.",
        )
    doc.status = payload.status
    doc.rejection_reason = (
        payload.rejection_reason if payload.status == DocumentStatus.REJECTED else None
    )
    doc.reviewed_by_user_id = admin.id
    doc.reviewed_at = datetime.now()
    audit_service.record(
        db,
        action="document.reviewed",
        entity_type="Document",
        actor=admin,
        entity_id=str(doc.id),
        details={"status": payload.status.value},
        request=request,
    )
    await db.commit()
    await db.refresh(doc)
    return _response(doc)


async def delete_document(
    db: AsyncSession, actor: User, document_id: uuid.UUID, request: Optional[Request] = None
) -> None:
    doc = await get_document(db, document_id)
    storage_key = doc.storage_key
    audit_service.record(
        db,
        action="document.deleted",
        entity_type="Document",
        actor=actor,
        entity_id=str(doc.id),
        request=request,
    )
    await db.delete(doc)
    await db.commit()
    await run_in_threadpool(storage_service.delete_document, storage_key)
