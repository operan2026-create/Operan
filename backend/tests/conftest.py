import base64
import os
import uuid

# Configure the environment BEFORE importing application modules.
os.environ.setdefault("SECRET_KEY", "unit-test-secret-key-0123456789abcdef0123456789abcdef")
os.environ.setdefault("CRYPTO_KEY", base64.b64encode(b"k" * 32).decode())
os.environ.setdefault(
    "PII_INDEX_KEY", "unit-test-pii-index-key-0123456789abcdef0123456789abcdef"
)
# Tests use the in-memory limiter even if the developer's .env points at Redis.
os.environ["REDIS_URL"] = ""
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("SQL_ECHO", "false")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.membership import Membership, MembershipStatus
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User, UserStatus
from app.security.encryption import crypto_manager
from app.security.hashing import get_password_hash
from app.security.jwt import create_access_token


@pytest.fixture(autouse=True)
def _reset_login_limiter_state():
    from app.services.login_limiter import login_limiter

    login_limiter.reset_local()
    yield
    login_limiter.reset_local()


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


def auth_headers(public_id: str) -> dict:
    token = create_access_token(data={"sub": public_id})
    return {"Authorization": f"Bearer {token}"}


def email_hash(email: str) -> str:
    from app.security.blind_index import email_index

    return email_index(email)


async def get_or_create_role(session, name: str) -> Role:
    result = await session.execute(
        select(Role).where(Role.name == name)
    )
    role = result.scalars().first()
    if role is None:
        role = Role(name=name, is_system=(name == "ADMIN"))
        session.add(role)
        await session.flush()
    return role


async def get_or_create_org(session, name: str) -> Organization:
    result = await session.execute(
        select(Organization).where(Organization.name == name)
    )
    org = result.scalars().first()
    if org is None:
        org = Organization(public_id=f"ORG-{uuid.uuid4().hex[:8].upper()}", name=name)
        session.add(org)
        await session.flush()
    return org


async def create_account(
    session_factory,
    email: str,
    role_name: str = "PARTICIPANT",
    org_name: str | None = None,
    password: str = "SenhaForte@2026",
    user_status: UserStatus = UserStatus.ACTIVE,
):
    """Creates a user with an active membership. Returns (user_id, org_id, public_id)."""
    async with session_factory() as session:
        role = await get_or_create_role(session, role_name)
        org = await get_or_create_org(session, org_name or f"Org {uuid.uuid4().hex[:6]}")
        user = User(
            public_id=f"USR-{uuid.uuid4().hex[:8].upper()}",
            email_hash=email_hash(email),
            email_encrypted=crypto_manager.encrypt_data(email.lower()),
            password_hash=get_password_hash(password),
            status=user_status,
        )
        session.add(user)
        await session.flush()
        session.add(
            Membership(
                user_id=user.id,
                organization_id=org.id,
                role_id=role.id,
                status=MembershipStatus.ACTIVE,
            )
        )
        await session.commit()
        return str(user.id), str(org.id), user.public_id
