from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
import hashlib

from app.core.deps import get_db, get_current_user
from app.models.user import User, UserStatus
from app.models.network import Professional, ProfessionalAvailability
from app.schemas.user import UserCreate, UserResponse
from app.schemas.collaborator import CollaboratorRegisterRequest, CollaboratorRegisterResponse
from app.services import user_service
from app.security.jwt import create_access_token
from app.security.encryption import crypto_manager

router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        user = await user_service.create_user(db, email=user_in.email, password=user_in.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    user.status = UserStatus.ACTIVE
    await db.commit()
    await db.refresh(user)

    token = create_access_token(data={"sub": user.public_id})
    return TokenResponse(access_token=token, token_type="bearer", user=UserResponse.model_validate(user))

@router.post("/register-collaborator", response_model=CollaboratorRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_collaborator(req: CollaboratorRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Public registration endpoint for collaborators (sent via link/invite).
    Creates User and encrypted Professional profile, then logs in immediately.
    """
    # 1. Create base user account
    try:
        user = await user_service.create_user(db, email=req.email, password=req.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    user.status = UserStatus.ACTIVE

    # 2. Check CPF duplication
    cpf_clean = "".join(filter(str.isdigit, req.cpf))
    cpf_hash = hashlib.sha256(cpf_clean.encode()).hexdigest()

    from sqlalchemy.future import select
    res = await db.execute(select(Professional).where(Professional.cpf_hash == cpf_hash))
    if res.scalars().first():
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este CPF já está cadastrado na rede OPERAN.")

    # 3. Create professional profile with AES-256-GCM encryption
    prof = Professional(
        user_id=user.id,
        full_name=req.full_name,
        cpf_hash=cpf_hash,
        cpf_encrypted=crypto_manager.encrypt_data(cpf_clean),
        phone_encrypted=crypto_manager.encrypt_data(req.phone),
        city=req.city,
        state=req.state.upper(),
        operational_radius_km=req.operational_radius_km,
        availability_status=ProfessionalAvailability.AVAILABLE,
        reputation_score=100.0,
    )
    db.add(prof)
    await db.commit()
    await db.refresh(prof)
    await db.refresh(user)

    token = create_access_token(data={"sub": user.public_id})
    return CollaboratorRegisterResponse(
        access_token=token,
        token_type="bearer",
        user_id=str(user.id),
        public_id=user.public_id,
        full_name=prof.full_name,
        city=prof.city,
        state=prof.state,
        status="ACTIVE",
    )

@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await user_service.authenticate_user(db, email=credentials.email, password=credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos."
        )
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Usuário não está ativo (status: {user.status.value})"
        )

    token = create_access_token(data={"sub": user.public_id})
    return TokenResponse(access_token=token, token_type="bearer", user=UserResponse.model_validate(user))

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
