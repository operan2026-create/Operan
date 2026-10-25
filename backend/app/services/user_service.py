"""
User service: handles all business logic for User creation,
lookup, and authentication. Keeps route handlers thin.
"""

import hashlib
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User, UserStatus
from app.security.encryption import crypto_manager
from app.security.hashing import get_password_hash, verify_password


def _hash_email(email: str) -> str:
    """Returns a deterministic SHA-256 hex digest of the normalised email."""
    return hashlib.sha256(email.lower().encode()).hexdigest()


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
    Looks up a User by the SHA-256 hash of their email address.

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
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
