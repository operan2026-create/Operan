import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_current_user_context,
    get_db,
    require_admin,
    require_professional,
    UserContext,
)
from app.models.user import User
from app.schemas.participant import (
    ProfessionalFunction,
    QualificationIssueRequest,
    QualificationRequirementCreate,
    QualificationRequirementResponse,
    QualificationResponse,
)
from app.services import qualification_service

router = APIRouter(prefix="/qualifications", tags=["Qualifications"])


@router.get("/requirements", response_model=list[QualificationRequirementResponse])
async def list_requirements(
    function_name: Optional[ProfessionalFunction] = Query(None),
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(get_current_user_context),
):
    return await qualification_service.list_requirements(
        db, function_name.value if function_name else None
    )


@router.post(
    "/requirements",
    response_model=QualificationRequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_requirement(
    payload: QualificationRequirementCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    return await qualification_service.create_requirement(
        db, context.user, payload, request
    )


@router.get("/me", response_model=list[QualificationResponse])
async def list_my_qualifications(
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_professional),
):
    return await qualification_service.list_qualifications(db, context.user.id)


@router.post("/{user_id}", response_model=QualificationResponse)
async def issue_qualification(
    user_id: uuid.UUID,
    payload: QualificationIssueRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    if payload.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id do corpo difere do user_id da rota.",
        )
    return await qualification_service.issue_qualification(
        db, context.user, payload, request
    )


@router.get("/{user_id}", response_model=list[QualificationResponse])
async def list_user_qualifications(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    context: UserContext = Depends(require_admin),
):
    target = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")
    return await qualification_service.list_qualifications(db, user_id)
