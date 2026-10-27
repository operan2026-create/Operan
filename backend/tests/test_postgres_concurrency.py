"""PostgreSQL-only concurrency tests.

SQLite serializes writes and ignores ``SELECT ... FOR UPDATE``, so the mission
assignment invariants can only be exercised against PostgreSQL. The tests use a
throw-away schema in the database pointed to by ``OPERAN_TEST_POSTGRES_URL`` and
are skipped when that variable is not set.

Example (PowerShell):
    $env:OPERAN_TEST_POSTGRES_URL="postgresql+asyncpg://<user>:<pass>@localhost:5433/<db>"
    .\\venv\\Scripts\\python.exe -m pytest tests/test_postgres_concurrency.py -q
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from app.core.database import Base
from app.models.mission import Mission, MissionStatus, MissionType
from app.models.network import Location
from app.models.participant import (
    ApplicationStatus,
    MissionApplication,
    MissionInvitation,
    MissionInvitationStatus,
)
from app.models.user import User
from app.schemas.participant import MissionApplicationDecision
from app.services import mission_service
from conftest import create_account

POSTGRES_URL = os.environ.get("OPERAN_TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="OPERAN_TEST_POSTGRES_URL is not configured",
)


@pytest_asyncio.fixture
async def pg_engine():
    schema = f"p0_test_{uuid.uuid4().hex[:10]}"

    bootstrap = create_async_engine(POSTGRES_URL)
    async with bootstrap.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    await bootstrap.dispose()

    engine = create_async_engine(
        POSTGRES_URL,
        connect_args={"server_settings": {"search_path": schema}},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()
    bootstrap = create_async_engine(POSTGRES_URL)
    async with bootstrap.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    await bootstrap.dispose()


async def _open_mission_with_applications(session_factory):
    admin_id, _, _ = await create_account(
        session_factory, "admin.pg@example.com", "ADMIN"
    )
    first_id, _, _ = await create_account(
        session_factory, "first.pg@example.com", "PARTICIPANT"
    )
    second_id, _, _ = await create_account(
        session_factory, "second.pg@example.com", "PARTICIPANT"
    )

    async with session_factory() as session:
        location = Location(
            name="Escola Concorrencia",
            address="Rua PG, 1",
            city="Salvador",
            state="BA",
        )
        session.add(location)
        await session.flush()
        mission = Mission(
            title="Missao Concorrente",
            mission_type=MissionType.VISTORIA,
            status=MissionStatus.OPEN,
            location_id=location.id,
            city="Salvador",
            state="BA",
        )
        session.add(mission)
        await session.flush()
        applications = [
            MissionApplication(
                mission_id=mission.id,
                user_id=uuid.UUID(first_id),
                status=ApplicationStatus.APPLIED,
                applied_at=datetime.now(timezone.utc),
            ),
            MissionApplication(
                mission_id=mission.id,
                user_id=uuid.UUID(second_id),
                status=ApplicationStatus.APPLIED,
                applied_at=datetime.now(timezone.utc),
            ),
        ]
        session.add_all(applications)
        await session.commit()
        return {
            "admin_id": uuid.UUID(admin_id),
            "mission_id": mission.id,
            "application_ids": [a.id for a in applications],
        }


async def _open_mission_with_invitations(session_factory):
    first_id, _, _ = await create_account(
        session_factory, "invited.first@example.com", "PARTICIPANT"
    )
    second_id, _, _ = await create_account(
        session_factory, "invited.second@example.com", "PARTICIPANT"
    )

    async with session_factory() as session:
        location = Location(
            name="Escola Convites",
            address="Rua PG, 2",
            city="Salvador",
            state="BA",
        )
        session.add(location)
        await session.flush()
        mission = Mission(
            title="Missao Convites Concorrentes",
            mission_type=MissionType.CONFIRMACAO,
            status=MissionStatus.OPEN,
            location_id=location.id,
            city="Salvador",
            state="BA",
        )
        session.add(mission)
        await session.flush()
        invitations = [
            MissionInvitation(
                mission_id=mission.id,
                user_id=uuid.UUID(first_id),
                status=MissionInvitationStatus.INVITED,
            ),
            MissionInvitation(
                mission_id=mission.id,
                user_id=uuid.UUID(second_id),
                status=MissionInvitationStatus.INVITED,
            ),
        ]
        session.add_all(invitations)
        await session.commit()
        return {
            "mission_id": mission.id,
            "users": [uuid.UUID(first_id), uuid.UUID(second_id)],
            "invitation_ids": [i.id for i in invitations],
        }


@pytest.mark.asyncio
async def test_concurrent_application_decisions_assign_only_one(pg_engine):
    session_factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    seeded = await _open_mission_with_applications(session_factory)

    async with session_factory() as session:
        admin = (
            await session.execute(select(User).where(User.id == seeded["admin_id"]))
        ).scalars().first()
        context = SimpleNamespace(is_admin=True, user=admin)

    async def decide(application_id):
        async with session_factory() as session:
            try:
                return await mission_service.decide_application(
                    session,
                    context,
                    application_id,
                    MissionApplicationDecision(status=ApplicationStatus.SELECTED),
                )
            except HTTPException as exc:
                await session.rollback()
                return exc

    results = await asyncio.gather(
        decide(seeded["application_ids"][0]),
        decide(seeded["application_ids"][1]),
    )

    failures = [r for r in results if isinstance(r, HTTPException)]
    successes = [r for r in results if not isinstance(r, HTTPException)]
    assert len(successes) == 1, results
    assert len(failures) == 1 and failures[0].status_code == 409

    async with session_factory() as session:
        mission = await session.get(Mission, seeded["mission_id"])
        applications = (
            await session.execute(
                select(MissionApplication).where(
                    MissionApplication.mission_id == seeded["mission_id"]
                )
            )
        ).scalars().all()
        selected = [
            a for a in applications if a.status == ApplicationStatus.SELECTED
        ]
        assert mission.status == MissionStatus.ASSIGNED
        assert mission.assigned_user_id == selected[0].user_id
        assert len(selected) == 1


@pytest.mark.asyncio
async def test_concurrent_invitation_acceptance_assigns_only_one(pg_engine):
    session_factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    seeded = await _open_mission_with_invitations(session_factory)

    async def respond(user_id, invitation_id):
        async with session_factory() as session:
            user = (
                await session.execute(select(User).where(User.id == user_id))
            ).scalars().first()
            try:
                return await mission_service.respond_mission_invitation(
                    session, user, invitation_id, accept=True
                )
            except HTTPException as exc:
                await session.rollback()
                return exc

    results = await asyncio.gather(
        respond(seeded["users"][0], seeded["invitation_ids"][0]),
        respond(seeded["users"][1], seeded["invitation_ids"][1]),
    )

    failures = [r for r in results if isinstance(r, HTTPException)]
    successes = [r for r in results if not isinstance(r, HTTPException)]
    assert len(successes) == 1, results
    assert len(failures) == 1 and failures[0].status_code == 409

    async with session_factory() as session:
        mission = await session.get(Mission, seeded["mission_id"])
        invitations = (
            await session.execute(
                select(MissionInvitation).where(
                    MissionInvitation.mission_id == seeded["mission_id"]
                )
            )
        ).scalars().all()
        accepted = [
            i for i in invitations if i.status == MissionInvitationStatus.ACCEPTED
        ]
        assert mission.status == MissionStatus.ASSIGNED
        assert mission.assigned_user_id == accepted[0].user_id
        assert len(accepted) == 1


@pytest.mark.asyncio
async def test_same_application_cannot_be_decided_twice(pg_engine):
    session_factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    seeded = await _open_mission_with_applications(session_factory)
    application_id = seeded["application_ids"][0]

    async with session_factory() as session:
        admin = (
            await session.execute(select(User).where(User.id == seeded["admin_id"]))
        ).scalars().first()
        context = SimpleNamespace(is_admin=True, user=admin)

    async def decide(status):
        async with session_factory() as session:
            try:
                return await mission_service.decide_application(
                    session,
                    context,
                    application_id,
                    MissionApplicationDecision(status=status),
                )
            except HTTPException as exc:
                await session.rollback()
                return exc

    results = await asyncio.gather(
        decide(ApplicationStatus.SELECTED),
        decide(ApplicationStatus.REJECTED),
    )

    failures = [r for r in results if isinstance(r, HTTPException)]
    successes = [r for r in results if not isinstance(r, HTTPException)]
    assert len(successes) == 1, results
    assert len(failures) == 1 and failures[0].status_code == 409

    async with session_factory() as session:
        mission = await session.get(Mission, seeded["mission_id"])
        application = await session.get(MissionApplication, application_id)
        assert application.status in {
            ApplicationStatus.SELECTED,
            ApplicationStatus.REJECTED,
        }
        if application.status == ApplicationStatus.SELECTED:
            assert mission.assigned_user_id == application.user_id
        else:
            assert mission.assigned_user_id is None
