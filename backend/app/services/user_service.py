"""
User service: handles all business logic for User creation,
lookup, and authentication. Keeps route handlers thin.
"""

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User, UserStatus
from app.security.blind_index import email_index
from app.security.encryption import crypto_manager
from app.security.hashing import get_password_hash, verify_password


def _hash_email(email: str) -> str:
    """Returns the keyed blind index for the normalised e-mail."""
    return email_index(email)


def email_lookup_hash(email: str) -> str:
    """Public accessor for the e-mail lookup hash (used by auth throttling)."""
    return _hash_email(email)


# Used to keep the timing of unknown-email logins close to known-email logins.
_DUMMY_PASSWORD_HASH = get_password_hash("operan-timing-equalisation")


def _generate_user_public_id() -> str:
    """Generates a short, human-readable public identifier for a user."""
    return "USR-" + str(uuid.uuid4())[:8].upper()


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User:
    """
    Creates a new user with a hashed password and encrypted + hashed email.

    - Checks for duplicate email via the email hash (constant-time-safe lookup).
    - Stores the encrypted email (AES-256-GCM) for decryption when needed.
    - New users start with PENDING status.

    :param db: Async database session.
    :param email: Plain-text email address.
    :param password: Plain-text password (will be Argon2id hashed).
    :return: Newly created and committed User ORM instance.
    :raises ValueError: If a user with the same email already exists.
    """
    email_hash = _hash_email(email)

    # Duplicate check
    existing = await get_user_by_email_hash(db, email)
    if existing:
        raise ValueError("A user with this email already exists.")

    user = User(
        public_id=_generate_user_public_id(),
        email_hash=email_hash,
        email_encrypted=crypto_manager.encrypt_data(email.lower()),
        password_hash=get_password_hash(password),
        status=UserStatus.PENDING,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_email_hash(
    db: AsyncSession,
    email: str,
) -> Optional[User]:
    """
    Looks up a User by the keyed blind index of their email address.

    :param db: Async database session.
    :param email: Plain-text email (will be hashed internally).
    :return: Matching User or None.
    """
    email_hash = _hash_email(email)
    result = await db.execute(select(User).where(User.email_hash == email_hash))
    return result.scalars().first()


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> Optional[User]:
    """
    Validates email + password credentials.

    :param db: Async database session.
    :param email: Plain-text email.
    :param password: Plain-text password.
    :return: User if credentials are valid, None otherwise.
    """
    user = await get_user_by_email_hash(db, email)
    if user is None:
        # Perform a dummy verification so unknown e-mails are not trivially
        # distinguishable by response time.
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def ensure_default_roles(db: AsyncSession):
    """Ensures foundational system roles exist in the database."""
    from app.models.role import Role

    default_roles = [
        {"name": "ADMIN", "is_system": True, "description": "Administrador Geral da Plataforma OPERAN"},
        {"name": "CLIENT_ADMIN", "is_system": False, "description": "Gestor da Banca / Organizadora Cliente"},
        {"name": "CLIENT_OPERATOR", "is_system": False, "description": "Operador da Banca / Organizadora Cliente"},
        {"name": "PARTICIPANT", "is_system": False, "description": "Colaborador Operacional / Participante de Campo"},
    ]
    for r in default_roles:
        res = await db.execute(select(Role).where(Role.name == r["name"]))
        if not res.scalars().first():
            db.add(Role(name=r["name"], is_system=r["is_system"], description=r["description"]))
    await db.commit()


async def get_or_create_admin_organization(db: AsyncSession):
    """Returns the internal platform organization for administrators."""
    from app.models.organization import Organization
    from app.services.organization_service import create_organization

    res = await db.execute(select(Organization).where(Organization.name == "OPERAN Matriz"))
    org = res.scalars().first()
    if not org:
        org = await create_organization(db, name="OPERAN Matriz")
    return org


async def assign_role_to_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    role_name: str,
    organization_id: Optional[uuid.UUID] = None,
):
    """Assigns or updates a user membership role in an organization."""
    from app.models.role import Role
    from app.models.membership import Membership, MembershipStatus

    await ensure_default_roles(db)
    role_res = await db.execute(select(Role).where(Role.name == role_name))
    role = role_res.scalars().first()
    if not role:
        raise ValueError(f"Role {role_name} não encontrada.")

    if not organization_id:
        admin_org = await get_or_create_admin_organization(db)
        organization_id = admin_org.id

    mem_res = await db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
        )
    )
    membership = mem_res.scalars().first()
    if membership:
        membership.role_id = role.id
        membership.status = MembershipStatus.ACTIVE
    else:
        membership = Membership(
            user_id=user_id,
            organization_id=organization_id,
            role_id=role.id,
            status=MembershipStatus.ACTIVE,
        )
        db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership

