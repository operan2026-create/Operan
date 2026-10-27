"""
Organization service: handles all business logic for Organization
creation, retrieval, and status management.
"""

import uuid
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.organization import Organization, OrganizationStatus
from app.security.blind_index import cnpj_index
from app.security.encryption import crypto_manager


def _hash_cnpj(cnpj: str) -> str:
    """Returns the keyed blind index of the normalised CNPJ."""
    return cnpj_index(cnpj)


def _generate_org_public_id() -> str:
    """Generates a short, human-readable public identifier for an organisation."""
    return "ORG-" + str(uuid.uuid4())[:8].upper()


async def create_organization(
    db: AsyncSession,
    name: str,
    cnpj: Optional[str] = None,
) -> Organization:
    """
    Creates a new Organization record.

    - If a CNPJ is provided it is blind-indexed (HMAC-SHA256) for duplicate-safe
      indexing and AES-256-GCM encrypted for storage.
    - New organisations start with ACTIVE status.

    :param db: Async database session.
    :param name: Human-readable organisation name.
    :param cnpj: Optional Brazilian company tax identifier (plain text).
    :return: Newly created and committed Organization ORM instance.
    """
    org = Organization(
        public_id=_generate_org_public_id(),
        name=name,
        cnpj_hash=_hash_cnpj(cnpj) if cnpj else None,
        cnpj_encrypted=crypto_manager.encrypt_data(cnpj) if cnpj else None,
        status=OrganizationStatus.ACTIVE,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


async def get_organizations(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
) -> List[Organization]:
    """
    Returns a paginated list of all organisations ordered by creation date (newest first).

    :param db: Async database session.
    :param skip: Number of records to skip.
    :param limit: Maximum number of records to return.
    :return: List of Organization ORM instances.
    """
    result = await db.execute(
        select(Organization)
        .order_by(Organization.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_organization_by_id(
    db: AsyncSession,
    org_id: str,
) -> Optional[Organization]:
    """
    Retrieves a single Organization by its UUID primary key.

    :param db: Async database session.
    :param org_id: UUID string of the organization.
    :return: Organization ORM instance or None.
    """
    try:
        parsed_id = uuid.UUID(str(org_id))
    except (ValueError, AttributeError):
        return None
    result = await db.execute(
        select(Organization).where(Organization.id == parsed_id)
    )
    return result.scalars().first()


async def get_organizations_by_ids(
    db: AsyncSession,
    organization_ids: List[uuid.UUID],
    skip: int = 0,
    limit: int = 20,
) -> List[Organization]:
    """Returns only the organizations explicitly allowed to the caller."""
    if not organization_ids:
        return []
    result = await db.execute(
        select(Organization)
        .where(Organization.id.in_(organization_ids))
        .order_by(Organization.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_organization_status(
    db: AsyncSession,
    org_id: str,
    new_status: OrganizationStatus,
) -> Optional[Organization]:
    """
    Updates the status of an existing Organization.

    :param db: Async database session.
    :param org_id: UUID string of the organization to update.
    :param new_status: The new OrganizationStatus value to apply.
    :return: Updated Organization ORM instance, or None if not found.
    """
    org = await get_organization_by_id(db, org_id)
    if org is None:
        return None
    org.status = new_status
    await db.commit()
    await db.refresh(org)
    return org
