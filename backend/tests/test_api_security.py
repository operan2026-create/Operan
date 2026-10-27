import base64
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings
from app.models.academy import (
    Certification,
    Course,
    CourseStatus,
    CourseVersion,
    Lesson,
    Module,
)
from app.models.membership import Membership, MembershipStatus
from app.models.mission import Mission, MissionStatus, MissionType
from app.models.network import Location, LocationStatus
from app.models.role import Role
from app.models.user import User, UserStatus
from app.security.blind_index import email_index
from conftest import auth_headers, create_account, get_or_create_org


async def _add_location(session_factory, org_id, name="Local", status=LocationStatus.DECLARADO):
    async with session_factory() as session:
        location = Location(
            organization_id=uuid.UUID(org_id) if org_id else None,
            name=name,
            address="Rua Teste, 100",
            city="Salvador",
            state="BA",
            status=status,
        )
        session.add(location)
        await session.commit()
        return str(location.id)


async def _add_mission(
    session_factory,
    location_id=None,
    assigned_user_id=None,
    status=MissionStatus.OPEN,
    city="Salvador",
    state="BA",
):
    async with session_factory() as session:
        mission = Mission(
            title="MissÃ£o de teste",
            mission_type=MissionType.VISTORIA,
            status=status,
            location_id=uuid.UUID(location_id) if location_id else None,
            assigned_user_id=uuid.UUID(assigned_user_id) if assigned_user_id else None,
            city=city,
            state=state,
            reward_amount=150.0,
        )
        session.add(mission)
        await session.commit()
        return str(mission.id)


async def _add_course_with_lessons(session_factory, org_id=None, status=CourseStatus.PUBLISHED, lessons=2):
    async with session_factory() as session:
        course = Course(
            title="Curso de teste",
            status=status,
            organization_id=uuid.UUID(org_id) if org_id else None,
        )
        session.add(course)
        await session.flush()
        version = CourseVersion(course_id=course.id, version_tag="v1.0", is_active=True)
        session.add(version)
        await session.flush()
        module = Module(course_version_id=version.id, title="MÃ³dulo", order_index=1)
        session.add(module)
        await session.flush()
        lesson_ids = []
        for index in range(lessons):
            lesson = Lesson(
                module_id=module.id,
                title=f"Aula {index + 1}",
                content_type="TEXT",
                content="ConteÃºdo",
                duration_minutes=5,
                order_index=index + 1,
            )
            session.add(lesson)
            await session.flush()
            lesson_ids.append(str(lesson.id))
        await session.commit()
        return str(version.id), lesson_ids


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #


async def test_anonymous_cannot_access_private_routes(client):
    for path in (
        "/api/v1/auth/me",
        "/api/v1/missions",
        "/api/v1/locations",
        "/api/v1/organizations",
        "/api/v1/academy/courses",
    ):
        response = await client.get(path)
        assert response.status_code == 401, path


async def test_login_valid_invalid_and_pending(client, session_factory):
    await create_account(
        session_factory, "active@operan.com.br", role_name="PARTICIPANT", password="SenhaForte@2026"
    )
    await create_account(
        session_factory,
        "pending@operan.com.br",
        role_name="PARTICIPANT",
        password="SenhaForte@2026",
        user_status=UserStatus.PENDING,
    )

    ok = await client.post(
        "/api/v1/auth/login",
        json={"email": "active@operan.com.br", "password": "SenhaForte@2026"},
    )
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "active@operan.com.br", "password": "SenhaErrada@2026"},
    )
    assert bad.status_code == 401

    pending = await client.post(
        "/api/v1/auth/login",
        json={"email": "pending@operan.com.br", "password": "SenhaForte@2026"},
    )
    assert pending.status_code == 403


async def test_public_registration_never_grants_admin(client, session_factory):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "first@operan.com.br", "password": "SenhaForte@2026"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["primary_role"] == "PARTICIPANT"
    assert body["user"]["roles"] == ["PARTICIPANT"]

    async with session_factory() as session:
        result = await session.execute(
            select(Role.name)
            .join(Membership, Membership.role_id == Role.id)
            .join(User, Membership.user_id == User.id)
            .where(User.email_hash == email_index("first@operan.com.br"))
        )
        assert result.scalars().all() == ["PARTICIPANT"]

    # Pending account token cannot access private resources.
    me = await client.get(
        "/api/v1/auth/me", headers=auth_headers(body["user"]["public_id"])
    )
    assert me.status_code == 403


# --------------------------------------------------------------------------- #
# Missions
# --------------------------------------------------------------------------- #


async def test_participant_cannot_create_mission(client, session_factory):
    _, _, public_id = await create_account(
        session_factory, "participant@operan.com.br", role_name="PARTICIPANT"
    )
    response = await client.post(
        "/api/v1/missions",
        json={"title": "X", "city": "Salvador", "state": "BA"},
        headers=auth_headers(public_id),
    )
    assert response.status_code == 403


async def test_client_cannot_target_another_organization(client, session_factory):
    _, org_a, public_id = await create_account(
        session_factory, "manager@operan.com.br", role_name="CLIENT_ADMIN"
    )
    _, org_b, _ = await create_account(
        session_factory, "other@operan.com.br", role_name="CLIENT_ADMIN"
    )
    location_b = await _add_location(session_factory, org_b)

    forbidden = await client.post(
        "/api/v1/missions",
        json={"title": "InvasÃ£o", "city": "X", "state": "BA", "location_id": location_b},
        headers=auth_headers(public_id),
    )
    assert forbidden.status_code == 403

    location_a = await _add_location(session_factory, org_a)
    created = await client.post(
        "/api/v1/missions",
        json={
            "title": "LegÃ­tima",
            "city": "Cidade Falsa",
            "state": "SP",
            "location_id": location_a,
            "status": "COMPLETED",
        },
        headers=auth_headers(public_id),
    )
    assert created.status_code == 201
    data = created.json()
    assert data["status"] == "OPEN"  # client cannot self-complete
    assert data["city"] == "Salvador"  # derived from verified location


async def test_participant_mission_isolation_and_transitions(client, session_factory):
    participant_id, org_a, participant = await create_account(
        session_factory, "p1@operan.com.br", role_name="PARTICIPANT"
    )
    _, _, other_participant = await create_account(
        session_factory, "p2@operan.com.br", role_name="PARTICIPANT"
    )
    _, _, admin = await create_account(session_factory, "admin@operan.com.br", role_name="ADMIN")
    _, _, manager = await create_account(
        session_factory, "manager2@operan.com.br", role_name="CLIENT_ADMIN", org_name=None
    )
    # Give manager access to org_a explicitly.
    async with session_factory() as session:
        role = (
            (await session.execute(select(Role).where(Role.name == "CLIENT_ADMIN")))
            .scalars()
            .first()
        )
        manager_user = (
            (await session.execute(select(User).where(User.public_id == manager)))
            .scalars()
            .first()
        )
        session.add(
            Membership(
                user_id=manager_user.id,
                organization_id=uuid.UUID(org_a),
                role_id=role.id,
                status=MembershipStatus.ACTIVE,
            )
        )
        await session.commit()

    location_a = await _add_location(session_factory, org_a)
    mission_id = await _add_mission(
        session_factory, location_a, assigned_user_id=participant_id, status=MissionStatus.ASSIGNED
    )

    # Other participant cannot see the assigned mission (not OPEN).
    listing = await client.get("/api/v1/missions", headers=auth_headers(other_participant))
    assert listing.status_code == 200
    assert all(m["id"] != mission_id for m in listing.json())

    # Other participant cannot change it.
    denied = await client.patch(
        f"/api/v1/missions/{mission_id}/status",
        json={"status": "IN_PROGRESS"},
        headers=auth_headers(other_participant),
    )
    assert denied.status_code == 403

    # Invalid transition ASSIGNED -> COMPLETED.
    invalid = await client.patch(
        f"/api/v1/missions/{mission_id}/status",
        json={"status": "COMPLETED"},
        headers=auth_headers(participant),
    )
    assert invalid.status_code == 409

    # Assigned participant may start.
    started = await client.patch(
        f"/api/v1/missions/{mission_id}/status",
        json={"status": "IN_PROGRESS"},
        headers=auth_headers(participant),
    )
    assert started.status_code == 200

    # Client manager cannot approve completion.
    manager_denied = await client.patch(
        f"/api/v1/missions/{mission_id}/status",
        json={"status": "COMPLETED"},
        headers=auth_headers(manager),
    )
    assert manager_denied.status_code == 403

    completed = await client.patch(
        f"/api/v1/missions/{mission_id}/status",
        json={"status": "COMPLETED"},
        headers=auth_headers(admin),
    )
    assert completed.status_code == 200


# --------------------------------------------------------------------------- #
# Locations
# --------------------------------------------------------------------------- #


async def test_location_tenant_isolation_and_admin_only_approval(client, session_factory):
    _, org_a, manager_a = await create_account(
        session_factory, "la@operan.com.br", role_name="CLIENT_ADMIN"
    )
    _, org_b, _ = await create_account(
        session_factory, "lb@operan.com.br", role_name="CLIENT_ADMIN"
    )
    _, _, participant = await create_account(
        session_factory, "lp@operan.com.br", role_name="PARTICIPANT"
    )
    _, _, admin = await create_account(session_factory, "ladmin@operan.com.br", role_name="ADMIN")

    loc_a = await _add_location(session_factory, org_a, "Local A")
    loc_b = await _add_location(session_factory, org_b, "Local B", LocationStatus.CONFIRMADO)

    listing = await client.get("/api/v1/locations", headers=auth_headers(manager_a))
    assert listing.status_code == 200
    ids = {row["id"] for row in listing.json()}
    assert loc_a in ids and loc_b not in ids

    participant_listing = await client.get(
        "/api/v1/locations", headers=auth_headers(participant)
    )
    participant_ids = {row["id"] for row in participant_listing.json()}
    assert participant_ids == {loc_b}  # only confirmed locations

    forbidden = await client.patch(
        f"/api/v1/locations/{loc_a}/status",
        json={"status": "VISTORIADO"},
        headers=auth_headers(participant),
    )
    assert forbidden.status_code == 403

    skip = await client.patch(
        f"/api/v1/locations/{loc_a}/status",
        json={"status": "CONFIRMADO"},
        headers=auth_headers(admin),
    )
    assert skip.status_code == 409

    inspected = await client.patch(
        f"/api/v1/locations/{loc_a}/status",
        json={"status": "VISTORIADO"},
        headers=auth_headers(admin),
    )
    assert inspected.status_code == 200

    confirmed = await client.patch(
        f"/api/v1/locations/{loc_a}/status",
        json={"status": "CONFIRMADO"},
        headers=auth_headers(admin),
    )
    assert confirmed.status_code == 200


# --------------------------------------------------------------------------- #
# Organizations / IDOR
# --------------------------------------------------------------------------- #


async def test_organization_idor_is_blocked(client, session_factory):
    _, org_a, manager_a = await create_account(
        session_factory, "oa@operan.com.br", role_name="CLIENT_ADMIN"
    )
    _, org_b, _ = await create_account(session_factory, "ob@operan.com.br", role_name="CLIENT_ADMIN")
    _, _, admin = await create_account(session_factory, "oadmin@operan.com.br", role_name="ADMIN")

    denied = await client.get(f"/api/v1/organizations/{org_b}", headers=auth_headers(manager_a))
    assert denied.status_code == 403

    own = await client.get(f"/api/v1/organizations/{org_a}", headers=auth_headers(manager_a))
    assert own.status_code == 200

    allowed = await client.get(f"/api/v1/organizations/{org_b}", headers=auth_headers(admin))
    assert allowed.status_code == 200


# --------------------------------------------------------------------------- #
# Academy / certification
# --------------------------------------------------------------------------- #


async def test_certification_requires_full_completion(client, session_factory):
    _, org_a, participant = await create_account(
        session_factory, "student@operan.com.br", role_name="PARTICIPANT"
    )
    _, _, client_user = await create_account(
        session_factory, "clientu@operan.com.br", role_name="CLIENT_ADMIN"
    )
    version_id, lesson_ids = await _add_course_with_lessons(session_factory, org_a)

    not_ready = await client.post(
        f"/api/v1/academy/versions/{version_id}/certify",
        headers=auth_headers(participant),
    )
    assert not_ready.status_code == 409

    first = await client.post(
        f"/api/v1/academy/lessons/{lesson_ids[0]}/complete",
        headers=auth_headers(participant),
    )
    assert first.status_code == 200

    still_not_ready = await client.post(
        f"/api/v1/academy/versions/{version_id}/certify",
        headers=auth_headers(participant),
    )
    assert still_not_ready.status_code == 409

    second = await client.post(
        f"/api/v1/academy/lessons/{lesson_ids[1]}/complete",
        headers=auth_headers(participant),
    )
    assert second.status_code == 200

    certified = await client.post(
        f"/api/v1/academy/versions/{version_id}/certify",
        headers=auth_headers(participant),
    )
    assert certified.status_code == 200
    assert certified.json()["score"] == 100.0

    duplicated = await client.post(
        f"/api/v1/academy/versions/{version_id}/certify",
        headers=auth_headers(participant),
    )
    assert duplicated.status_code == 200
    assert duplicated.json()["id"] == certified.json()["id"]

    client_denied_complete = await client.post(
        f"/api/v1/academy/lessons/{lesson_ids[0]}/complete",
        headers=auth_headers(client_user),
    )
    assert client_denied_complete.status_code == 403

    client_denied_cert = await client.post(
        f"/api/v1/academy/versions/{version_id}/certify",
        headers=auth_headers(client_user),
    )
    assert client_denied_cert.status_code == 403


async def test_courses_are_scoped_between_organizations(client, session_factory):
    _, org_a, manager_a = await create_account(
        session_factory, "ca@operan.com.br", role_name="CLIENT_ADMIN"
    )
    _, org_b, _ = await create_account(
        session_factory, "cb@operan.com.br", role_name="CLIENT_ADMIN"
    )
    version_a, _ = await _add_course_with_lessons(
        session_factory, org_a, status=CourseStatus.DRAFT
    )
    version_b, _ = await _add_course_with_lessons(
        session_factory, org_b, status=CourseStatus.DRAFT
    )

    async with session_factory() as session:
        from app.models.academy import CourseVersion

        course_a = (
            await session.execute(
                select(CourseVersion.course_id).where(CourseVersion.id == uuid.UUID(version_a))
            )
        ).scalar()
        course_b = (
            await session.execute(
                select(CourseVersion.course_id).where(CourseVersion.id == uuid.UUID(version_b))
            )
        ).scalar()

    listing = await client.get("/api/v1/academy/courses", headers=auth_headers(manager_a))
    assert listing.status_code == 200
    ids = {row["id"] for row in listing.json()}
    assert str(course_a) in ids and str(course_b) not in ids


async def test_participant_cannot_certify_draft_course(client, session_factory):
    _, org_a, participant = await create_account(
        session_factory, "draftstudent@operan.com.br", role_name="PARTICIPANT"
    )
    version_id, lesson_ids = await _add_course_with_lessons(
        session_factory, org_a, status=CourseStatus.DRAFT
    )

    for lesson_id in lesson_ids:
        response = await client.post(
            f"/api/v1/academy/lessons/{lesson_id}/complete",
            headers=auth_headers(participant),
        )
        assert response.status_code == 409

    certify = await client.post(
        f"/api/v1/academy/versions/{version_id}/certify",
        headers=auth_headers(participant),
    )
    assert certify.status_code == 409


# --------------------------------------------------------------------------- #
# Roles and configuration
# --------------------------------------------------------------------------- #


async def test_role_is_system_is_not_client_controlled(client, session_factory):
    _, _, admin = await create_account(session_factory, "radmin@operan.com.br", role_name="ADMIN")
    response = await client.post(
        "/api/v1/roles",
        json={"name": "AUDITOR", "description": "teste", "is_system": True},
        headers=auth_headers(admin),
    )
    assert response.status_code == 201

    async with session_factory() as session:
        role = (
            (await session.execute(select(Role).where(Role.name == "AUDITOR"))).scalars().first()
        )
        assert role.is_system is False


def test_insecure_settings_are_rejected():
    valid_crypto = base64.b64encode(b"z" * 32).decode()

    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="INSECURE_CHANGE_ME_IN_PRODUCTION", CRYPTO_KEY=valid_crypto)

    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="short", CRYPTO_KEY=valid_crypto)

    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="a" * 40, CRYPTO_KEY=base64.b64encode(b"short").decode())

    settings = Settings(SECRET_KEY="b" * 40, CRYPTO_KEY=valid_crypto)
    assert settings.SQL_ECHO is False
