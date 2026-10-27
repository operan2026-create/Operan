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
from app.models.participant import JourneyEnrollment, JourneyStatus, JourneyType, PersonProfile, ProfessionalQualification
from app.security.jwt import bearer_scheme, get_current_user, verify_token

ADMIN_ROLE = "ADMIN"
CLIENT_MANAGER_ROLES = {"CLIENT_ADMIN"}
CLIENT_ROLES = {"CLIENT_ADMIN", "CLIENT_OPERATOR"}


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
            detail="Conta não ativa. Ative sua conta para continuar.",
        )
    return current_user


class UserContext:
    """
    Rich user context holding the active User, their Memberships (with roles and orgs),
    and their Professional profile.
    """

    def __init__(
        self,
        user: User,
        memberships: List[Membership],
        professional: Optional[Professional] = None,
        person_profile: Optional[PersonProfile] = None,
        journeys: Optional[List[JourneyEnrollment]] = None,
        qualifications: Optional[List[ProfessionalQualification]] = None,
    ):
        self.user = user
        self.memberships = memberships
        self.professional = professional
        self.person_profile = person_profile
        self.journeys = journeys or []
        self.qualifications = qualifications or []

    def _active_memberships(self) -> List[Membership]:
        return [m for m in self.memberships if m.status == MembershipStatus.ACTIVE]

    def _has_role(self, role_names) -> bool:
        return any(
            m.role and m.role.name.upper() in role_names
            for m in self._active_memberships()
        )

    @property
    def is_admin(self) -> bool:
        # Somente o papel ADMIN concede administracao da plataforma.
        # is_system por si só não implica privilégio.
        return self._has_role({ADMIN_ROLE})

    @property
    def is_client_manager(self) -> bool:
        return self._has_role(CLIENT_MANAGER_ROLES)

    @property
    def is_client(self) -> bool:
        return self._has_role(CLIENT_ROLES)

    @property
    def active_journeys(self) -> List[JourneyEnrollment]:
        return [j for j in self.journeys if j.status == JourneyStatus.ACTIVE]

    @property
    def is_professional(self) -> bool:
        return any(j.journey_type == JourneyType.PROFESSIONALS for j in self.active_journeys)

    @property
    def is_representative(self) -> bool:
        return any(j.journey_type == JourneyType.LOCATIONS for j in self.active_journeys)

    @property
    def is_participant(self) -> bool:
        return (
            self.is_professional
            or self.is_representative
            or self.professional is not None
            or self._has_role({"PARTICIPANT"})
        )

    @property
    def primary_role(self) -> str:
        if self.is_admin:
            return "ADMIN"
        if self.is_client_manager:
            return "CLIENT"
        if self.is_client:
            return "CLIENT"
        if self.is_participant:
            return "PARTICIPANT"
        return "USER"

    @property
    def client_organization_ids(self) -> List[UUID]:
        """Organizações em que o usuário atua como cliente/gestor."""
        return list(
            {
                m.organization_id
                for m in self._active_memberships()
                if m.role and m.role.name.upper() in CLIENT_ROLES
            }
        )

    @property
    def active_organization_ids(self) -> List[UUID]:
        return [m.organization_id for m in self._active_memberships()]

    @property
    def primary_organization_id(self) -> Optional[UUID]:
        org_ids = self.client_organization_ids
        return org_ids[0] if org_ids else None

    def has_client_org_access(self, organization_id: UUID) -> bool:
        return self.is_admin or organization_id in self.client_organization_ids

    def is_manager_of(self, organization_id: UUID) -> bool:
        if self.is_admin:
            return True
        return any(
            m.organization_id == organization_id
            and m.role
            and m.role.name.upper() in CLIENT_MANAGER_ROLES
            for m in self._active_memberships()
        )

    def to_user_response(self) -> dict:
        roles_list = []
        memberships_info = []
        for m in self._active_memberships():
            if m.role:
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

        journeys_info = [
            {
                "id": j.id,
                "journey_type": j.journey_type.value,
                "status": j.status.value,
                "activated_at": j.activated_at,
                "requirements_met_at": j.requirements_met_at,
                "created_at": j.created_at,
            }
            for j in self.journeys
        ]
        qualifications_info = [
            {
                "id": q.id,
                "user_id": q.user_id,
                "function_name": q.function_name,
                "status": q.status.value,
                "certification_id": q.certification_id,
                "course_version_id": q.course_version_id,
                "issued_at": q.issued_at,
                "expires_at": q.expires_at,
                "suspended_reason": q.suspended_reason,
            }
            for q in self.qualifications
        ]

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
            "journeys": journeys_info,
            "qualifications": qualifications_info,
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

    profile_res = await db.execute(
        select(PersonProfile).where(PersonProfile.user_id == current_user.id)
    )
    person_profile = profile_res.scalars().first()

    journey_res = await db.execute(
        select(JourneyEnrollment).where(JourneyEnrollment.user_id == current_user.id)
    )
    journeys = list(journey_res.scalars().all())

    qualification_res = await db.execute(
        select(ProfessionalQualification).where(
            ProfessionalQualification.user_id == current_user.id
        )
    )
    qualifications = list(qualification_res.scalars().all())

    return UserContext(
        user=current_user,
        memberships=memberships,
        professional=prof,
        person_profile=person_profile,
        journeys=journeys,
        qualifications=qualifications,
    )


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


async def require_client_manager(
    context: UserContext = Depends(get_current_user_context),
) -> UserContext:
    """Restricts write operations to client managers (not operators) or admins."""
    if not context.is_client_manager and not context.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: operação restrita a gestores da organização cliente.",
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


async def require_professional(
    context: UserContext = Depends(get_current_user_context),
) -> UserContext:
    if not context.is_professional and not context.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: jornada profissional nao ativa.",
        )
    return context


async def require_representative(
    context: UserContext = Depends(get_current_user_context),
) -> UserContext:
    if not context.is_representative and not context.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: jornada de representante nao ativa.",
        )
    return context


async def get_optional_current_user(
    credentials=Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if credentials is None:
        return None
    payload = verify_token(credentials.credentials)
    public_id = payload.get("sub")
    if not public_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
        )
    user = (await db.execute(select(User).where(User.public_id == public_id))).scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials"
        )
    return user
