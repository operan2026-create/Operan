import base64
import hashlib
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select, text

from app.models.academy import Certification, CertificationStatus, Course, CourseVersion
from app.models.mission import Mission, MissionStatus, MissionType
from app.models.network import Location, LocationStatus, Professional
from app.models.participant import (
    JourneyEnrollment,
    JourneyStatus,
    JourneyType,
    PersonProfile,
    ProfessionalQualification,
    RepresentativeSchoolLink,
)
from app.models.user import User, UserStatus
from app.core.config import settings
from app.security.encryption import crypto_manager
from app.services import storage_service
from conftest import auth_headers, create_account, email_hash, get_or_create_org

TEST_AVATAR_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
)


async def _location(session_factory, org_id, status=LocationStatus.DECLARADO):
    async with session_factory() as session:
        location = Location(
            organization_id=uuid.UUID(org_id),
            name="Escola Teste",
            address="Rua A, 10",
            city="Salvador",
            state="BA",
            status=status,
            reliability_score=100,
        )
        session.add(location)
        await session.commit()
        return str(location.id)


async def _create_invitation(client, admin_pub, journey_type, location_id=None, email=None):
    response = await client.post(
        "/api/v1/invitations",
        headers=auth_headers(admin_pub),
        json={
            "email": email or f"pessoa.{uuid.uuid4().hex[:8]}@example.com",
            "journey_type": journey_type,
            "location_id": location_id,
            "expires_in_days": 7,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _accept(client, token, headers=None, password="SenhaForte@2026"):
    payload = {
        "privacy_consent": True,
        "full_name": "Pessoa Teste",
        "cpf": "12345678901",
        "phone": "71999999999",
        "city": "Salvador",
        "state": "BA",
        "birth_date": "1990-01-01",
        "avatar_base64": TEST_AVATAR_BASE64,
        "avatar_mime_type": "image/png",
    }
    if password:
        payload["password"] = password
    response = await client.post(
        f"/api/v1/invitations/{token}/accept", json=payload, headers=headers or {}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_invitation_creates_one_account_with_independent_journeys(
    client, session_factory
):
    admin_id, org_id, admin_pub = await create_account(
        session_factory, "admin.jornadas@example.com", "ADMIN"
    )
    location_id = await _location(session_factory, org_id)
    email = f"unico.{uuid.uuid4().hex[:8]}@example.com"

    first = await _create_invitation(client, admin_pub, "LOCATIONS", location_id, email)
    accepted = await _accept(client, first["token"])
    first_user = accepted["user"]
    assert first_user["primary_role"] == "PARTICIPANT"
    assert [j["journey_type"] for j in first_user["journeys"]] == ["LOCATIONS"]

    second = await _create_invitation(client, admin_pub, "PROFESSIONALS", email=email)
    accepted_again = await _accept(
        client,
        second["token"],
        headers={"Authorization": f"Bearer {accepted['access_token']}"},
        password=None,
    )
    same_user = accepted_again["user"]
    assert same_user["public_id"] == first_user["public_id"]
    assert {j["journey_type"] for j in same_user["journeys"]} == {
        "LOCATIONS",
        "PROFESSIONALS",
    }

    async with session_factory() as session:
        users = (
            await session.execute(select(User).where(User.email_hash == email_hash(email)))
        ).scalars().all()
        profiles = (
            await session.execute(
                select(PersonProfile).where(
                    PersonProfile.user_id == uuid.UUID(first_user["id"])
                )
            )
        ).scalars().all()
        journeys = (
            await session.execute(
                select(JourneyEnrollment).where(
                    JourneyEnrollment.user_id == uuid.UUID(first_user["id"])
                )
            )
        ).scalars().all()
        link = (
            await session.execute(
                select(RepresentativeSchoolLink).where(
                    RepresentativeSchoolLink.representative_user_id
                    == uuid.UUID(first_user["id"])
                )
            )
        ).scalars().first()
    assert len(users) == 1
    assert len(profiles) == 1
    assert len(journeys) == 2
    assert link is not None

    account = await client.get(
        "/api/v1/account/me",
        headers={"Authorization": f"Bearer {accepted_again['access_token']}"},
    )
    assert account.status_code == 200, account.text
    assert account.json()["profile"]["email"] == email


@pytest.mark.asyncio
async def test_representative_workflow_and_final_release_permissions(
    client, session_factory
):
    admin_id, org_id, admin_pub = await create_account(
        session_factory, "admin.workflow@example.com", "ADMIN"
    )
    client_admin_id, client_org_id, client_pub = await create_account(
        session_factory,
        "gestor.workflow@example.com",
        "CLIENT_ADMIN",
        org_name=f"Org Workflow {uuid.uuid4().hex[:6]}",
    )
    location_id = await _location(session_factory, client_org_id)

    invite = await _create_invitation(
        client, client_pub, "LOCATIONS", location_id
    )
    accepted = await _accept(client, invite["token"])
    rep_headers = {"Authorization": f"Bearer {accepted['access_token']}"}

    submitted = await client.post(
        f"/api/v1/representatives/schools/{location_id}/submit/CAPTURE",
        headers=rep_headers,
    )
    assert submitted.status_code == 201, submitted.text
    forbidden_release = await client.post(
        f"/api/v1/representatives/schools/{location_id}/submit/RELEASE",
        headers=rep_headers,
    )
    assert forbidden_release.status_code == 403

    approved = await client.post(
        f"/api/v1/representatives/locations/{location_id}/stages/CAPTURE/decision",
        headers=auth_headers(client_pub),
        json={"approve": True, "notes": "ok"},
    )
    assert approved.status_code == 200, approved.text

    for stage in ("DOCUMENTATION", "INSPECTION"):
        submitted = await client.post(
            f"/api/v1/representatives/schools/{location_id}/submit/{stage}",
            headers=rep_headers,
        )
        assert submitted.status_code == 201, submitted.text
        decided = await client.post(
            f"/api/v1/representatives/locations/{location_id}/stages/{stage}/decision",
            headers=auth_headers(client_pub),
            json={"approve": True},
        )
        assert decided.status_code == 200, decided.text

    release_submission = await client.post(
        f"/api/v1/representatives/locations/{location_id}/stages/RELEASE/submit",
        headers=auth_headers(client_pub),
    )
    assert release_submission.status_code == 201, release_submission.text
    release = await client.post(
        f"/api/v1/representatives/locations/{location_id}/stages/RELEASE/decision",
        headers=auth_headers(client_pub),
        json={"approve": True},
    )
    assert release.status_code == 200, release.text

    async with session_factory() as session:
        location = (
            await session.execute(select(Location).where(Location.id == uuid.UUID(location_id)))
        ).scalars().first()
    assert location.status == LocationStatus.CONFIRMADO


async def _professional_account(session_factory, email, org_id):
    user_id, _, public_id = await create_account(
        session_factory, email, "PARTICIPANT", org_name=f"Org {uuid.uuid4().hex[:6]}"
    )
    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.id == uuid.UUID(user_id)))).scalars().first()
        session.add(
            JourneyEnrollment(
                user_id=user.id,
                journey_type=JourneyType.PROFESSIONALS,
                status=JourneyStatus.ACTIVE,
                activated_at=datetime.now(timezone.utc),
            )
        )
        profile = PersonProfile(
            user_id=user.id,
            full_name="Profissional Teste",
            cpf_hash=hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest(),
            cpf_encrypted=crypto_manager.encrypt_data("98765432100"),
            phone_encrypted=crypto_manager.encrypt_data("71988887777"),
            city="Salvador",
            state="BA",
            profile_completed=True,
        )
        session.add(profile)
        await session.flush()
        session.add(
            Professional(
                user_id=user.id,
                full_name=profile.full_name,
                cpf_hash=profile.cpf_hash,
                cpf_encrypted=profile.cpf_encrypted,
                phone_encrypted=profile.phone_encrypted,
                city=profile.city,
                state=profile.state,
            )
        )
        await session.commit()
    return user_id, public_id


async def _course_version(session_factory):
    async with session_factory() as session:
        course = Course(title="Curso Fiscal", status="PUBLISHED")
        session.add(course)
        await session.flush()
        version = CourseVersion(course_id=course.id, version_tag="v1.0", is_active=True)
        session.add(version)
        await session.commit()
        return str(version.id)


@pytest.mark.asyncio
async def test_qualification_requires_certification_and_active_journey(
    client, session_factory
):
    admin_id, org_id, admin_pub = await create_account(
        session_factory, "admin.qual@example.com", "ADMIN"
    )
    professional_id, professional_pub = await _professional_account(
        session_factory, "prof.qual@example.com", org_id
    )
    version_id = await _course_version(session_factory)

    requirement = await client.post(
        "/api/v1/qualifications/requirements",
        headers=auth_headers(admin_pub),
        json={
            "course_version_id": version_id,
            "function_name": "FISCAL_SALA",
            "is_required": True,
            "validity_days": 365,
        },
    )
    assert requirement.status_code == 201, requirement.text

    missing_cert = await client.post(
        f"/api/v1/qualifications/{professional_id}",
        headers=auth_headers(admin_pub),
        json={
            "user_id": professional_id,
            "function_name": "FISCAL_SALA",
        },
    )
    assert missing_cert.status_code == 409

    async with session_factory() as session:
        session.add(
            Certification(
                user_id=uuid.UUID(professional_id),
                course_version_id=uuid.UUID(version_id),
                status=CertificationStatus.VALID,
            )
        )
        await session.commit()

    issued = await client.post(
        f"/api/v1/qualifications/{professional_id}",
        headers=auth_headers(admin_pub),
        json={
            "user_id": professional_id,
            "function_name": "FISCAL_SALA",
            "validity_days": 365,
        },
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == "ACTIVE"

    mine = await client.get(
        "/api/v1/qualifications/me", headers=auth_headers(professional_pub)
    )
    assert mine.status_code == 200, mine.text
    assert mine.json()[0]["function_name"] == "FISCAL_SALA"


@pytest.mark.asyncio
async def test_mission_application_and_selection_are_scoped(client, session_factory):
    professional_id, professional_pub = await _professional_account(
        session_factory, "prof.missao@example.com", None
    )
    client_admin_id, org_id, client_pub = await create_account(
        session_factory,
        "gestor.missao@example.com",
        "CLIENT_ADMIN",
        org_name=f"Org Missao {uuid.uuid4().hex[:6]}",
    )
    location_id = await _location(session_factory, org_id)

    async with session_factory() as session:
        session.add(
            ProfessionalQualification(
                user_id=uuid.UUID(professional_id),
                function_name="FISCAL_SALA",
                status="ACTIVE",
            )
        )
        mission = Mission(
            title="Missao Fiscal",
            mission_type=MissionType.VISTORIA,
            status=MissionStatus.OPEN,
            location_id=uuid.UUID(location_id),
            city="Salvador",
            state="BA",
            reward_amount=200,
            required_function="FISCAL_SALA",
        )
        session.add(mission)
        await session.commit()
        mission_id = str(mission.id)

    applied = await client.post(
        f"/api/v1/missions/{mission_id}/applications",
        headers=auth_headers(professional_pub),
    )
    assert applied.status_code == 201, applied.text
    application_id = applied.json()["id"]

    candidates = await client.get(
        f"/api/v1/missions/{mission_id}/applications",
        headers=auth_headers(client_pub),
    )
    assert candidates.status_code == 200, candidates.text
    assert len(candidates.json()) == 1

    decided = await client.patch(
        f"/api/v1/missions/applications/{application_id}/decision",
        headers=auth_headers(client_pub),
        json={"status": "SELECTED", "notes": "Selecionado"},
    )
    assert decided.status_code == 200, decided.text

    async with session_factory() as session:
        mission = (
            await session.execute(select(Mission).where(Mission.id == uuid.UUID(mission_id)))
        ).scalars().first()
    assert mission.status == MissionStatus.ASSIGNED
    assert str(mission.assigned_user_id) == professional_id

@pytest.mark.asyncio
async def test_location_invitation_requires_linked_school(client, session_factory):
    _, _, admin_pub = await create_account(
        session_factory, "admin.sem.escola@example.com", "ADMIN"
    )

    response = await client.post(
        "/api/v1/invitations",
        headers=auth_headers(admin_pub),
        json={
            "email": "representante.sem.escola@example.com",
            "journey_type": "LOCATIONS",
            "expires_in_days": 7,
        },
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_direct_mission_invitation_acceptance_and_network_filter(
    client, session_factory
):
    professional_id, professional_pub = await _professional_account(
        session_factory, "prof.convite@example.com", None
    )
    client_admin_id, org_id, client_pub = await create_account(
        session_factory,
        "gestor.convite@example.com",
        "CLIENT_ADMIN",
        org_name=f"Org Convite {uuid.uuid4().hex[:6]}",
    )
    location_id = await _location(session_factory, org_id)

    async with session_factory() as session:
        session.add(
            ProfessionalQualification(
                user_id=uuid.UUID(professional_id),
                function_name="FISCAL_SALA",
                status="ACTIVE",
            )
        )
        mission = Mission(
            title="Missao Convite Direto",
            mission_type=MissionType.VISTORIA,
            status=MissionStatus.OPEN,
            location_id=uuid.UUID(location_id),
            city="Salvador",
            state="BA",
            reward_amount=250,
            required_function="FISCAL_SALA",
        )
        session.add(mission)
        await session.commit()
        mission_id = str(mission.id)

    network = await client.get(
        "/api/v1/professionals?function=FISCAL_SALA",
        headers=auth_headers(client_pub),
    )
    assert network.status_code == 200, network.text
    assert not any(
        row["user_id"] == professional_id for row in network.json()
    )

    invited = await client.post(
        f"/api/v1/missions/{mission_id}/invitations",
        headers=auth_headers(client_pub),
        json={"user_ids": [professional_id], "message": "Convite prioritario"},
    )
    assert invited.status_code == 201, invited.text
    assert invited.json()[0]["status"] == "INVITED"

    mine = await client.get(
        "/api/v1/missions/invitations/me",
        headers=auth_headers(professional_pub),
    )
    assert mine.status_code == 200, mine.text
    assert len(mine.json()) == 1
    invitation_id = mine.json()[0]["id"]

    accepted = await client.post(
        f"/api/v1/missions/invitations/{invitation_id}/accept",
        headers=auth_headers(professional_pub),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "ACCEPTED"

    async with session_factory() as session:
        mission = (
            await session.execute(select(Mission).where(Mission.id == uuid.UUID(mission_id)))
        ).scalars().first()
    assert mission.status == MissionStatus.ASSIGNED
    assert str(mission.assigned_user_id) == professional_id

    network = await client.get(
        "/api/v1/professionals?function=FISCAL_SALA",
        headers=auth_headers(client_pub),
    )
    assert network.status_code == 200, network.text
    assert any(
        row["user_id"] == professional_id and "FISCAL_SALA" in row["qualifications"]
        for row in network.json()
    )


async def _create_public_invitation(
    client,
    admin_pub,
    journey_type,
    location_id=None,
    *,
    max_uses=None,
    label="Link publico teste",
):
    response = await client.post(
        "/api/v1/invitations/public",
        headers=auth_headers(admin_pub),
        json={
            "label": label,
            "journey_type": journey_type,
            "location_id": location_id,
            "expires_in_days": 7,
            "max_uses": max_uses,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _accept_public(client, token, email, *, headers=None, password="SenhaForte@2026"):
    payload = {
        "email": email,
        "privacy_consent": True,
        "full_name": "Pessoa Link Publico",
        "cpf": "".join(str(uuid.uuid4().int)[:11]),
        "phone": "71999999999",
        "city": "Salvador",
        "state": "BA",
        "avatar_base64": TEST_AVATAR_BASE64,
        "avatar_mime_type": "image/png",
    }
    if password:
        payload["password"] = password
    return await client.post(
        f"/api/v1/invitations/public/{token}/accept",
        json=payload,
        headers=headers or {},
    )


@pytest.mark.asyncio
async def test_public_invitation_is_reusable_until_max_uses(client, session_factory):
    admin_id, org_id, admin_pub = await create_account(
        session_factory, "admin.publico@example.com", "ADMIN"
    )
    link = await _create_public_invitation(
        client, admin_pub, "PROFESSIONALS", max_uses=1
    )

    validated = await client.get(f"/api/v1/invitations/public/validate/{link['token']}")
    assert validated.status_code == 200, validated.text
    data = validated.json()
    assert data["valid"] is True
    assert data["status"] == "ACTIVE"
    assert data["requires_account"] is True
    assert data["label"] == "Link publico teste"
    assert data["uses_count"] == 0

    first_email = f"publico.{uuid.uuid4().hex[:8]}@example.com"
    accepted = await _accept_public(client, link["token"], first_email)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["user"]["primary_role"] == "PARTICIPANT"

    exhausted = await client.get(f"/api/v1/invitations/public/validate/{link['token']}")
    assert exhausted.status_code == 200, exhausted.text
    assert exhausted.json()["valid"] is False
    assert exhausted.json()["uses_count"] == 1

    exceeded = await _accept_public(
        client, link["token"], f"publico.{uuid.uuid4().hex[:8]}@example.com"
    )
    assert exceeded.status_code == 409, exceeded.text

    listed = await client.get(
        "/api/v1/invitations/public", headers=auth_headers(admin_pub)
    )
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json() if item["id"] == link["id"])
    assert row["uses_count"] == 1
    assert row["status"] == "EXPIRED"
    assert row["accept_path"] is None


@pytest.mark.asyncio
async def test_public_invitation_can_be_revoked_and_accepts_logged_user(
    client, session_factory
):
    admin_id, org_id, admin_pub = await create_account(
        session_factory, "admin.publico.revoga@example.com", "ADMIN"
    )
    link = await _create_public_invitation(client, admin_pub, "PROFESSIONALS")

    user_email = f"existente.{uuid.uuid4().hex[:8]}@example.com"
    user_id, _user_org, user_pub = await create_account(
        session_factory,
        user_email,
        "PARTICIPANT",
    )
    authenticated = await client.get(
        f"/api/v1/invitations/public/validate/{link['token']}",
        headers=auth_headers(user_pub),
    )
    assert authenticated.status_code == 200, authenticated.text
    assert authenticated.json()["requires_account"] is False

    accepted = await _accept_public(
        client,
        link["token"],
        user_email,
        headers=auth_headers(user_pub),
        password=None,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["user"]["public_id"] == user_pub
    assert "PROFESSIONALS" in {
        journey["journey_type"] for journey in accepted.json()["user"]["journeys"]
    }

    revoked = await client.post(
        f"/api/v1/invitations/public/{link['id']}/revoke",
        headers=auth_headers(admin_pub),
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "REVOKED"
    assert revoked.json()["accept_path"] is None

    invalid = await client.get(f"/api/v1/invitations/public/validate/{link['token']}")
    assert invalid.status_code == 200, invalid.text
    assert invalid.json()["valid"] is False
    assert invalid.json()["status"] == "REVOKED"

    denied = await _accept_public(
        client, link["token"], f"novo.{uuid.uuid4().hex[:8]}@example.com"
    )
    assert denied.status_code == 409, denied.text


@pytest.mark.asyncio
async def test_public_invitation_creates_new_participant_when_logged_with_other_email(
    client, session_factory
):
    admin_id, org_id, admin_pub = await create_account(
        session_factory, "admin.publico.outro@example.com", "ADMIN"
    )
    link = await _create_public_invitation(client, admin_pub, "PROFESSIONALS")
    participant_email = f"novo.participante.{uuid.uuid4().hex[:8]}@example.com"

    accepted = await _accept_public(
        client,
        link["token"],
        participant_email,
        headers=auth_headers(admin_pub),
    )
    assert accepted.status_code == 200, accepted.text
    user = accepted.json()["user"]
    assert user["public_id"] != admin_pub
    assert user["email"] == participant_email
    assert user["primary_role"] == "PARTICIPANT"


@pytest.mark.asyncio
async def test_public_location_link_creates_representative_link(client, session_factory):
    admin_id, org_id, admin_pub = await create_account(
        session_factory, "admin.publico.escola@example.com", "ADMIN"
    )
    location_id = await _location(session_factory, org_id)
    link = await _create_public_invitation(
        client, admin_pub, "LOCATIONS", location_id, label="Escola publica"
    )
    assert link["location_name"] == "Escola Teste"
    assert link["organization_name"] is not None

    validated = await client.get(f"/api/v1/invitations/public/validate/{link['token']}")
    assert validated.status_code == 200, validated.text
    assert validated.json()["location_name"] == "Escola Teste"

    email = f"escola.{uuid.uuid4().hex[:8]}@example.com"
    accepted = await _accept_public(client, link["token"], email)
    assert accepted.status_code == 200, accepted.text
    user = accepted.json()["user"]
    assert "LOCATIONS" in {journey["journey_type"] for journey in user["journeys"]}

    async with session_factory() as session:
        representative = (
            await session.execute(
                select(RepresentativeSchoolLink).where(
                    RepresentativeSchoolLink.representative_user_id
                    == uuid.UUID(user["id"]),
                    RepresentativeSchoolLink.location_id == uuid.UUID(location_id),
                )
            )
        ).scalars().first()
    assert representative is not None


@pytest.mark.asyncio
async def test_invitation_requires_profile_photo(client, session_factory):
    admin_id, org_id, admin_pub = await create_account(
        session_factory, "admin.foto.obrigatoria@example.com", "ADMIN"
    )
    link = await _create_public_invitation(client, admin_pub, "PROFESSIONALS")
    response = await client.post(
        f"/api/v1/invitations/public/{link['token']}/accept",
        json={
            "email": f"semfoto.{uuid.uuid4().hex[:8]}@example.com",
            "password": "SenhaForte@2026",
            "privacy_consent": True,
            "full_name": "Pessoa Sem Foto",
            "cpf": "".join(str(uuid.uuid4().int)[:11]),
            "phone": "71999999999",
            "city": "Salvador",
            "state": "BA",
        },
    )
    assert response.status_code == 422, response.text
    assert "Foto de perfil" in response.text


@pytest.mark.asyncio
async def test_participant_data_and_documents_are_encrypted_at_rest(
    client, session_factory, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_DIR", str(tmp_path))
    admin_id, org_id, admin_pub = await create_account(
        session_factory, "admin.cripto@example.com", "ADMIN"
    )
    invite = await _create_invitation(client, admin_pub, "PROFESSIONALS")
    accepted = await _accept(client, invite["token"])
    user_id = uuid.UUID(accepted["user"]["id"])
    headers = {"Authorization": f"Bearer {accepted['access_token']}"}

    async with session_factory() as session:
        profile = (
            await session.execute(
                text(
                    "SELECT full_name, city, state, birth_date, avatar_data "
                    "FROM person_profiles WHERE user_id=:user_id"
                ),
                {"user_id": user_id.hex},
            )
        ).mappings().first()
        professional = (
            await session.execute(
                text(
                    "SELECT full_name, city, state FROM professionals WHERE user_id=:user_id"
                ),
                {"user_id": user_id.hex},
            )
        ).mappings().first()
    assert profile is not None and professional is not None
    for field in ("full_name", "city", "state"):
        assert profile[field] != "Pessoa Teste"
        assert crypto_manager.decrypt_data(profile[field]) == (
            "BA" if field == "state" else ("Salvador" if field == "city" else "Pessoa Teste")
        )
        assert professional[field] != "Pessoa Teste"
    assert profile["birth_date"] is not None
    assert profile["birth_date"] != "1990-01-01"
    assert crypto_manager.decrypt_data(profile["birth_date"]) == "1990-01-01"
    assert crypto_manager.decrypt_data(profile["avatar_data"]) == TEST_AVATAR_BASE64

    content = base64.b64decode(TEST_AVATAR_BASE64)
    uploaded = await client.post(
        "/api/v1/documents/me",
        headers=headers,
        files={"file": ("documento-secreto.png", content, "image/png")},
        data={"document_type": "OTHER"},
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]

    async with session_factory() as session:
        document_row = (
            await session.execute(
                text("SELECT file_name, storage_key FROM documents WHERE id=:document_id"),
                {"document_id": uuid.UUID(document_id).hex},
            )
        ).mappings().first()
    assert document_row is not None
    assert document_row["file_name"] != "documento-secreto.png"
    assert crypto_manager.decrypt_data(document_row["file_name"]) == "documento-secreto.png"
    stored = storage_service.document_path(document_row["storage_key"]).read_bytes()
    assert stored.startswith(storage_service.ENCRYPTED_FILE_MAGIC)
    assert content not in stored

    downloaded = await client.get(
        f"/api/v1/documents/{document_id}/download", headers=headers
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == content

    avatar = await client.get("/api/v1/account/avatar", headers=headers)
    assert avatar.status_code == 200, avatar.text
    assert avatar.content == content
