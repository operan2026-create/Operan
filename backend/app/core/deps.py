"""
Common FastAPI dependencies used across the API layer.

Re-exports get_db and provides typed user dependencies so routers
only need to import from a single location.
"""

from fastapi import Depends, HTTPException, status

from app.core.database import get_db  # noqa: F401  (re-exported for convenience)
from app.models.user import User, UserStatus
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
