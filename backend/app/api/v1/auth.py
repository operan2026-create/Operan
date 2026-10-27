from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from app.core.deps import get_db, get_current_user_context, UserContext
from app.models.user import UserStatus
from app.schemas.user import UserCreate, UserResponse
from app.schemas.collaborator import CollaboratorRegisterRequest, CollaboratorRegisterResponse
from app.services import audit_service, user_service
from app.services.login_limiter import client_ip, login_limiter
from app.security.jwt import create_access_token

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
    """
    Public self-registration.

    The account always starts as PENDING and receives the PARTICIPANT role.
    Privileged roles are never granted from public input, and the first user
    does not become an administrator automatically.
    """
    try:
        user = await user_service.create_user(db, email=user_in.email, password=user_in.password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não foi possível concluir o cadastro com os dados informados."
        )

    # New accounts stay PENDING until an administrator activates them.
    await user_service.assign_role_to_user(db, user.id, "PARTICIPANT")

    context = await get_current_user_context(current_user=user, db=db)
    user_resp = context.to_user_response()
    token = create_access_token(data={"sub": user.public_id, "role": context.primary_role})
    return TokenResponse(access_token=token, token_type="bearer", user=UserResponse.model_validate(user_resp))

@router.post("/register-collaborator", response_model=CollaboratorRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_collaborator(req: CollaboratorRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Cadastro publico desativado: a entrada ocorre apenas por convite."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Cadastro publico desativado. Solicite um convite da escola ou da administracao OPERAN.",
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = client_ip(request)
    account_hash = user_service.email_lookup_hash(credentials.email)

    decision = await login_limiter.check(ip=ip, account_hash=account_hash)
    if not decision.allowed:
        audit_service.record(
            db,
            action="auth.login_blocked",
            entity_type="User",
            actor=None,
            details={"scope": decision.reason},
            request=request,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de acesso. Tente novamente em alguns instantes.",
            headers={"Retry-After": str(max(1, decision.retry_after))},
        )

    user = await user_service.authenticate_user(
        db, email=credentials.email, password=credentials.password
    )
    if not user:
        await login_limiter.record_failure(ip=ip, account_hash=account_hash)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
        )
    if user.status != UserStatus.ACTIVE:
        await login_limiter.record_failure(ip=ip, account_hash=account_hash)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta indisponivel. Procure o suporte da plataforma.",
        )

    await login_limiter.record_success(ip=ip, account_hash=account_hash)
    context = await get_current_user_context(current_user=user, db=db)
    user_resp = context.to_user_response()
    token = create_access_token(data={"sub": user.public_id, "role": context.primary_role})
    return TokenResponse(access_token=token, token_type="bearer", user=UserResponse.model_validate(user_resp))

@router.get("/me", response_model=UserResponse)
async def get_me(context: UserContext = Depends(get_current_user_context)):
    return UserResponse.model_validate(context.to_user_response())

