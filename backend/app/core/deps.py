"""
Common FastAPI dependencies used across the API layer.

Re-exports get_db and provides typed user & authorization dependencies
so routers only need to import from a single location.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db  # noqa: F401  (re-exported for convenience)
from app.models.user import User, UserStatus
from app.models.membership import Membership, MembershipStatus
from app.models.network import Professional
from app.security.jwt import get_current_user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency that ensures the authenticated user has ACTIVE status.

    :raises HTTPException 403: If the account is not active.
    """
    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active. "
            f"Current status: {current_user.status.value}",
        )
    return current_user


class UserContext:
    """
    Rich user context holding the active User, their active Memberships (with roles and orgs),
    and their Professional profile.
    """

    def __init__(
        self,
        user: User,
        memberships: List[Membership],
        professional: Optional[Professional] = None,
    ):
        self.user = user
        self.memberships = memberships
        self.professional = professional

    @property
    def is_admin(self) -> bool:
        return any(
            (m.role and (m.role.name.upper() == "ADMIN" or m.role.is_system))
            for m in self.memberships
            if m.status == MembershipStatus.ACTIVE
        )

    @property
    def is_client(self) -> bool:
        return any(
            (m.role and (m.role.name.upper().startswith("CLIENT") or "CLIENT" in m.role.name.upper()))
            for m in self.memberships
            if m.status == MembershipStatus.ACTIVE
        )

    @property
    def is_participant(self) -> bool:
        return self.professional is not None or any(
            (m.role and m.role.name.upper() == "PARTICIPANT")
            for m in self.memberships
            if m.status == MembershipStatus.ACTIVE
        ) or (not self.is_admin and not self.is_client)

    @property
    def primary_role(self) -> str:
        if self.is_admin:
            return "ADMIN"
        if self.is_client:
            return "CLIENT"
        return "PARTICIPANT"

    @property
    def client_organization_ids(self) -> List[UUID]:
        return [
            m.organization_id
            for m in self.memberships
            if m.status == MembershipStatus.ACTIVE
        ]

    @property
    def primary_organization_id(self) -> Optional[UUID]:
        org_ids = self.client_organization_ids
        return org_ids[0] if org_ids else None

    def to_user_response(self) -> dict:
        roles_list = []
        memberships_info = []
        for m in self.memberships:
            if m.status == MembershipStatus.ACTIVE and m.role:
                roles_list.append(m.role.name)
                memberships_info.append({
                    "id": m.id,
                    "organization_id": m.organization_id,
                    "organization_name": m.organization.name if m.organization else None,
                    "role_id": m.role_id,
                    "role_name": m.role.name,
                    "status": m.status.value if hasattr(m.status, "value") else str(m.status),
                })

        prof_info = None
        if self.professional:
            prof_info = {
                "id": self.professional.id,
                "full_name": self.professional.full_name,
                "city": self.professional.city,
                "state": self.professional.state,
                "operational_radius_km": self.professional.operational_radius_km,
                "availability_status": self.professional.availability_status.value if hasattr(self.professional.availability_status, "value") else str(self.professional.availability_status),
                "reputation_score": float(self.professional.reputation_score) if self.professional.reputation_score else 100.0,
            }

        return {
            "id": self.user.id,
            "public_id": self.user.public_id,
            "email": self.user.email,
            "status": self.user.status,
            "mfa_enabled": self.user.mfa_enabled,
            "created_at": self.user.created_at,
            "updated_at": self.user.updated_at,
            "primary_role": self.primary_role,
            "roles": list(set(roles_list)) if roles_list else [self.primary_role],
            "memberships": memberships_info,
            "professional": prof_info,
        }


async def get_current_user_context(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserContext:
    """
    FastAPI dependency that loads full user authorization context:
    memberships, roles, organizations, and professional profile.
    """
    stmt = (
        select(Membership)
        .where(Membership.user_id == current_user.id)
        .options(selectinload(Membership.role), selectinload(Membership.organization))
    )
    res = await db.execute(stmt)
    memberships = list(res.scalars().all())

    prof_res = await db.execute(
        select(Professional).where(Professional.user_id == current_user.id)
    )
    prof = prof_res.scalars().first()

    return UserContext(user=current_user, memberships=memberships, professional=prof)


async def require_admin(
    context: UserContext = Depends(get_current_user_context),
) -> UserContext:
    """Restricts route to OPERAN Platform Administrators."""
    if not context.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: operação restrita a Administradores da OPERAN.",
        )
    return context


async def require_client(
    context: UserContext = Depends(get_current_user_context),
) -> UserContext:
    """Restricts route to Client / Organizing Institution Members or Admins."""
    if not context.is_client and not context.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: operação restrita a Clientes da OPERAN.",
        )
    return context


async def require_participant(
    context: UserContext = Depends(get_current_user_context),
) -> UserContext:
    """Restricts route to Operational Participants or Admins."""
    if not context.is_participant and not context.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: operação restrita a Participantes / Colaboradores.",
        )
    return context

