"""Explicit, auditable bootstrap of a platform administrator.

The administrative password is never accepted as a command-line argument.
Provide it through the ``OPERAN_ADMIN_PASSWORD`` environment variable or type
it interactively (hidden input).

Usage (PowerShell):
    python create_admin.py admin@operan.local
    python create_admin.py admin@operan.local --activate-existing

Existing accounts are never assigned a new password. A non-active account is
only reactivated with the explicit ``--activate-existing`` flag.
"""

import argparse
import asyncio
import getpass
import os
import sys

from app.core.database import async_session
from app.models.user import User, UserStatus
from app.services import audit_service, user_service

PASSWORD_ENV = "OPERAN_ADMIN_PASSWORD"
MIN_PASSWORD_LENGTH = 8


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or promote an OPERAN administrator."
    )
    parser.add_argument("email", help="Administrator e-mail address")
    parser.add_argument(
        "--activate-existing",
        action="store_true",
        help="Explicitly reactivate an existing PENDING/BLOCKED account",
    )
    return parser


def resolve_password() -> str:
    password = os.environ.get(PASSWORD_ENV)
    if password is None:
        password = getpass.getpass("Administrator password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"Password must contain at least {MIN_PASSWORD_LENGTH} characters."
        )
    return password


async def main(email: str, password: str, *, activate_existing: bool = False) -> User:
    email = email.strip().lower()
    if not email:
        raise SystemExit("E-mail is required.")

    async with async_session() as db:
        await user_service.ensure_default_roles(db)

        user = await user_service.get_user_by_email_hash(db, email)
        created = user is None
        if user is None:
            user = await user_service.create_user(db, email=email, password=password)
        elif user.status != UserStatus.ACTIVE and not activate_existing:
            raise SystemExit(
                "Existing account is not active. Re-run with --activate-existing "
                "to reactivate it explicitly."
            )

        # The bootstrap is the explicit administrative operation that may
        # activate a new or flagged account. It never rewrites a password.
        if user.status != UserStatus.ACTIVE:
            user.status = UserStatus.ACTIVE
            await db.commit()
            await db.refresh(user)

        await user_service.assign_role_to_user(db, user.id, "ADMIN")

        audit_service.record(
            db,
            action="admin.bootstrap",
            entity_type="User",
            actor=None,
            entity_id=str(user.id),
            details={"created": created, "activate_existing": activate_existing},
        )
        await db.commit()

        print(f"{'Created' if created else 'Promoted'} ADMIN user")
        print(f"public_id={user.public_id}")
        print("role=ADMIN")
        return user


def cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    password = resolve_password()
    try:
        asyncio.run(
            main(args.email, password, activate_existing=args.activate_existing)
        )
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(cli())
