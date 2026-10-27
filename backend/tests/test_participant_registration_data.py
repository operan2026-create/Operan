import uuid
from datetime import datetime, timedelta, timezone

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models.mission import Mission, MissionType
from app.models.participant import (
    Invitation,
    InvitationPurpose,
    ParticipantBankAccount,
    ParticipantClientLink,
    ParticipantClientLinkStatus,
    ParticipantFamilyMember,
    PersonProfile,
    RegistrationDraft,
)
from app.schemas.participant import InvitationAcceptRequest
from app.security.blind_index import cpf_index
from app.security.encryption import crypto_manager
from app.services import invitation_service
from conftest import auth_headers, create_account

TEST_AVATAR_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
)


def _future() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=7)


async def _raw_row(session_factory, sql: str, params: dict):
    async with session_factory() as session:
        return (await session.execute(text(sql), params)).mappings().first()


async def _participant_profile(
    session_factory, email: str, cpf: str, *, full_name: str = "Pessoa Teste"
):
    user_id, _, public_id = await create_account(session_factory, email)
    async with session_factory() as session:
        profile = PersonProfile(
            user_id=uuid.UUID(user_id),
            full_name=full_name,
            cpf_hash=cpf_index(cpf),
            cpf_encrypted=crypto_manager.encrypt_data(cpf),
            phone_encrypted=crypto_manager.encrypt_data("71999998888"),
            city="Salvador",
            state="BA",
            profile_completed=True,
        )
        session.add(profile)
        await session.commit()
        return uuid.UUID(user_id), public_id


async def _link(session_factory, user_id: uuid.UUID, org_id: str):
    async with session_factory() as session:
        session.add(
            ParticipantClientLink(
                user_id=user_id,
                organization_id=uuid.UUID(org_id),
                status=ParticipantClientLinkStatus.ACTIVE,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_bank_and_family_pii_are_encrypted_at_rest(session_factory):
    user_id, _, _ = await create_account(session_factory, "pii.bank@example.com")

    async with session_factory() as session:
        bank = ParticipantBankAccount(
            user_id=uuid.UUID(user_id),
            bank_code="001",
            bank_name="Banco do Brasil",
            branch="1234",
            account_number="987654-3",
            holder_name="Maria Silva",
            holder_cpf="123.456.789-09",
            account_fingerprint="fingerprint-1",
            is_primary=True,
        )
        family = ParticipantFamilyMember(
            user_id=uuid.UUID(user_id),
            full_name="Joao Silva",
            kinship="FILHO",
            phone="71999999999",
            cpf="987.654.321-00",
            is_legal_guardian=True,
            notes="Autorizado pelo responsavel legal",
        )
        session.add_all([bank, family])
        await session.commit()
        bank_id = str(bank.id)
        family_id = str(family.id)

    bank_row = await _raw_row(
        session_factory,
        "SELECT bank_name, branch, account_number, holder_name, holder_cpf, pix_key "
        "FROM participant_bank_accounts WHERE id=:id",
        {"id": uuid.UUID(bank_id).hex},
    )
    family_row = await _raw_row(
        session_factory,
        'SELECT "relationship", full_name, phone, cpf, notes '
        "FROM participant_family_members WHERE id=:id",
        {"id": uuid.UUID(family_id).hex},
    )

    assert bank_row is not None and family_row is not None
    assert bank_row["bank_name"] != "Banco do Brasil"
    assert crypto_manager.decrypt_data(bank_row["bank_name"]) == "Banco do Brasil"
    assert crypto_manager.decrypt_data(bank_row["branch"]) == "1234"
    assert crypto_manager.decrypt_data(bank_row["account_number"]) == "987654-3"
    assert crypto_manager.decrypt_data(bank_row["holder_name"]) == "Maria Silva"
    assert crypto_manager.decrypt_data(bank_row["holder_cpf"]) == "123.456.789-09"
    assert bank_row["pix_key"] is None

    assert family_row["relationship"] == "FILHO"
    assert family_row["full_name"] != "Joao Silva"
    assert crypto_manager.decrypt_data(family_row["full_name"]) == "Joao Silva"
    assert crypto_manager.decrypt_data(family_row["phone"]) == "71999999999"
    assert crypto_manager.decrypt_data(family_row["cpf"]) == "987.654.321-00"
    assert (
        crypto_manager.decrypt_data(family_row["notes"])
        == "Autorizado pelo responsavel legal"
    )

    async with session_factory() as session:
        bank = await session.get(ParticipantBankAccount, uuid.UUID(bank_id))
        family = await session.get(ParticipantFamilyMember, uuid.UUID(family_id))
        assert bank is not None and bank.bank_name == "Banco do Brasil"
        assert family is not None and family.kinship == "FILHO"
        assert family.full_name == "Joao Silva"


@pytest.mark.asyncio
async def test_registration_draft_payload_is_encrypted_at_rest(session_factory):
    user_id, _, _ = await create_account(session_factory, "draft.owner@example.com")
    payload = '{"full_name":"Pessoa Rascunho","cpf":"123.456.789-09"}'

    async with session_factory() as session:
        draft = RegistrationDraft(
            token_hash="draft-token-hash",
            token_prefix="draft-pr",
            user_id=uuid.UUID(user_id),
            data_encrypted=payload,
            current_step=3,
            expires_at=_future(),
        )
        session.add(draft)
        await session.commit()
        draft_id = str(draft.id)

    row = await _raw_row(
        session_factory,
        "SELECT token_hash, data_encrypted, current_step FROM registration_drafts "
        "WHERE id=:id",
        {"id": uuid.UUID(draft_id).hex},
    )
    assert row is not None
    assert row["token_hash"] == "draft-token-hash"
    assert row["data_encrypted"] != payload
    assert crypto_manager.decrypt_data(row["data_encrypted"]) == payload
    assert row["current_step"] == 3

    async with session_factory() as session:
        draft = await session.get(RegistrationDraft, uuid.UUID(draft_id))
        assert draft is not None and draft.data_encrypted == payload


@pytest.mark.asyncio
async def test_invitation_purpose_and_mission_are_persisted(session_factory):
    _, org_id, _ = await create_account(session_factory, "invite.purpose@example.com")

    async with session_factory() as session:
        mission = Mission(
            title="Missao de campo",
            mission_type=MissionType.CAPTACAO,
            organization_id=uuid.UUID(org_id),
            city="Salvador",
            state="BA",
        )
        session.add(mission)
        await session.flush()
        invitation = Invitation(
            token_hash="purpose-token-hash",
            token_prefix="purpose",
            email_hash="email-hash",
            email_encrypted=crypto_manager.encrypt_data("convidado@example.com"),
            journey_type="PROFESSIONALS",
            purpose=InvitationPurpose.MISSION_PARTICIPANT,
            mission_id=mission.id,
            required_data_categories=["PROFILE", "BANK"],
            organization_id=uuid.UUID(org_id),
            expires_at=_future(),
        )
        session.add(invitation)
        await session.commit()
        invitation_id = str(invitation.id)
        mission_id = str(mission.id)

    async with session_factory() as session:
        invitation = await session.get(Invitation, uuid.UUID(invitation_id))
        assert invitation is not None
        assert invitation.purpose == InvitationPurpose.MISSION_PARTICIPANT
        assert str(invitation.mission_id) == mission_id
        assert invitation.required_data_categories == ["PROFILE", "BANK"]


@pytest.mark.asyncio
async def test_participant_client_link_is_unique_per_user_and_organization(
    session_factory,
):
    user_id, org_id, _ = await create_account(
        session_factory, "linked.participant@example.com"
    )

    async with session_factory() as session:
        session.add(
            ParticipantClientLink(
                user_id=uuid.UUID(user_id),
                organization_id=uuid.UUID(org_id),
                purpose="OPERATIONAL",
            )
        )
        await session.commit()

    async with session_factory() as session:
        session.add(
            ParticipantClientLink(
                user_id=uuid.UUID(user_id),
                organization_id=uuid.UUID(org_id),
                purpose="MISSION",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_account_bank_account_endpoints_mask_data_and_enforce_ownership(
    client, session_factory
):
    _, _, user_public_id = await create_account(
        session_factory, "bank.api.owner@example.com"
    )
    _, _, other_public_id = await create_account(
        session_factory, "bank.api.other@example.com"
    )
    headers = auth_headers(user_public_id)

    created = await client.post(
        "/api/v1/account/bank-accounts",
        headers=headers,
        json={
            "bank_code": "001",
            "bank_name": "Banco do Brasil",
            "branch": "1234-5",
            "account_number": "987654-3",
            "holder_name": "Maria Silva",
            "holder_cpf": "123.456.789-09",
            "pix_key_type": "EMAIL",
            "pix_key": "maria@example.com",
        },
    )
    assert created.status_code == 201, created.text
    account = created.json()
    assert account["account_number_masked"] == "****6543"
    assert account["holder_cpf_masked"] == "***.***.***-09"
    assert account["pix_key_masked"] != "maria@example.com"
    assert account["is_primary"] is True
    assert account["status"] == "PENDING"

    listed = await client.get("/api/v1/account/bank-accounts", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [account["id"]]

    forbidden = await client.patch(
        f"/api/v1/account/bank-accounts/{account['id']}",
        headers=auth_headers(other_public_id),
        json={"holder_name": "Outra Pessoa"},
    )
    assert forbidden.status_code == 404

    updated = await client.patch(
        f"/api/v1/account/bank-accounts/{account['id']}",
        headers=headers,
        json={"account_number": "111111-1"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["account_number_masked"] == "****1111"

    removed = await client.delete(
        f"/api/v1/account/bank-accounts/{account['id']}", headers=headers
    )
    assert removed.status_code == 204, removed.text


@pytest.mark.asyncio
async def test_account_family_member_endpoints_mask_data_and_enforce_ownership(
    client, session_factory
):
    _, _, user_public_id = await create_account(
        session_factory, "family.api.owner@example.com"
    )
    _, _, other_public_id = await create_account(
        session_factory, "family.api.other@example.com"
    )
    headers = auth_headers(user_public_id)

    created = await client.post(
        "/api/v1/account/family-members",
        headers=headers,
        json={
            "full_name": "Joao Silva",
            "kinship": "filho",
            "phone": "71999999999",
            "cpf": "987.654.321-00",
            "is_legal_guardian": True,
            "notes": "Autorizado pelo responsavel legal",
        },
    )
    assert created.status_code == 201, created.text
    member = created.json()
    assert member["kinship"] == "FILHO"
    assert member["phone_masked"].endswith("9999")
    assert member["cpf_masked"] == "***.***.***-00"

    forbidden = await client.patch(
        f"/api/v1/account/family-members/{member['id']}",
        headers=auth_headers(other_public_id),
        json={"notes": "Alteracao indevida"},
    )
    assert forbidden.status_code == 404

    updated = await client.patch(
        f"/api/v1/account/family-members/{member['id']}",
        headers=headers,
        json={"kinship": "dependente"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["kinship"] == "DEPENDENTE"

    removed = await client.delete(
        f"/api/v1/account/family-members/{member['id']}", headers=headers
    )
    assert removed.status_code == 204, removed.text


@pytest.mark.asyncio
async def test_invitation_acceptance_creates_active_client_link(session_factory):
    _, org_id, _ = await create_account(
        session_factory, "invite.link.org@example.com", org_name="Org Vinculo"
    )
    mission_id = None
    async with session_factory() as session:
        mission = Mission(
            title="Missao com vinculo",
            mission_type=MissionType.CAPTACAO,
            organization_id=uuid.UUID(org_id),
            city="Salvador",
            state="BA",
        )
        session.add(mission)
        await session.flush()
        mission_id = mission.id
        invitation = Invitation(
            token_hash=invitation_service.hash_token("link-token"),
            token_prefix="link-tok",
            email_hash=invitation_service.hash_email("linked@example.com"),
            email_encrypted=crypto_manager.encrypt_data("linked@example.com"),
            journey_type="PROFESSIONALS",
            purpose=InvitationPurpose.MISSION_PARTICIPANT,
            mission_id=mission_id,
            organization_id=uuid.UUID(org_id),
            expires_at=_future(),
        )
        session.add(invitation)
        await session.commit()

    async with session_factory() as session:
        user, _ = await invitation_service.accept_invitation(
            session,
            token="link-token",
            payload=InvitationAcceptRequest(
                email="linked@example.com",
                password="SenhaForte@2026",
                full_name="Pessoa Vinculada",
                cpf="111.222.333-44",
                phone="71988887777",
                city="Salvador",
                state="BA",
                privacy_consent=True,
                avatar_base64=TEST_AVATAR_BASE64,
                avatar_mime_type="image/png",
            ),
        )
        user_id = user.id

    async with session_factory() as session:
        link = (
            await session.execute(
                select(ParticipantClientLink).where(
                    ParticipantClientLink.user_id == user_id
                )
            )
        ).scalars().first()
        assert link is not None
        assert str(link.organization_id) == org_id
        assert str(link.source_mission_id) == str(mission_id)
        assert link.purpose == InvitationPurpose.MISSION_PARTICIPANT.value
        assert link.status.value == "ACTIVE"


@pytest.mark.asyncio
async def test_participant_directory_is_scoped_by_active_client_link(
    client, session_factory
):
    _, org_id, client_public_id = await create_account(
        session_factory,
        "directory.client@example.com",
        "CLIENT_ADMIN",
        org_name="Org Diretorio",
    )
    _, _, admin_public_id = await create_account(
        session_factory, "directory.admin@example.com", "ADMIN"
    )
    linked_id, linked_public_id = await _participant_profile(
        session_factory, "directory.linked@example.com", "11111111111", full_name="Pessoa Vinculada"
    )
    unlinked_id, _ = await _participant_profile(
        session_factory, "directory.unlinked@example.com", "22222222222", full_name="Pessoa Solta"
    )
    await _link(session_factory, linked_id, org_id)

    client_headers = auth_headers(client_public_id)
    listed = await client.get("/api/v1/participants", headers=client_headers)
    assert listed.status_code == 200, listed.text
    assert [item["public_id"] for item in listed.json()] == [linked_public_id]

    detail = await client.get(
        f"/api/v1/participants/{linked_id}", headers=client_headers
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["full_name"] == "Pessoa Vinculada"
    assert body["cpf_masked"] == "***.***.***-11"
    assert [org["organization_id"] for org in body["organizations"]] == [org_id]
    assert "bank_accounts" not in body
    assert "family_members" not in body

    hidden = await client.get(
        f"/api/v1/participants/{unlinked_id}", headers=client_headers
    )
    assert hidden.status_code == 404

    admin_list = await client.get(
        "/api/v1/participants", headers=auth_headers(admin_public_id)
    )
    assert admin_list.status_code == 200, admin_list.text
    assert {item["public_id"] for item in admin_list.json()} == {
        linked_public_id,
        await _public_id_of(session_factory, unlinked_id),
    }

    forbidden = await client.get(
        "/api/v1/participants", headers=auth_headers(linked_public_id)
    )
    assert forbidden.status_code == 403


async def _public_id_of(session_factory, user_id: uuid.UUID) -> str:
    async with session_factory() as session:
        from app.models.user import User

        user = await session.get(User, user_id)
        return user.public_id


@pytest.mark.asyncio
async def test_admin_records_participant_validation_and_updates_status(
    client, session_factory
):
    user_id, participant_public_id = await _participant_profile(
        session_factory, "validation.participant@example.com", "33333333333"
    )
    _, _, admin_public_id = await create_account(
        session_factory, "validation.admin@example.com", "ADMIN"
    )

    denied = await client.post(
        f"/api/v1/participants/{user_id}/validations",
        headers=auth_headers(participant_public_id),
        json={"scope": "PROFILE", "status": "VALIDATED"},
    )
    assert denied.status_code == 403

    created = await client.post(
        f"/api/v1/participants/{user_id}/validations",
        headers=auth_headers(admin_public_id),
        json={
            "scope": "PROFILE",
            "status": "VALIDATED",
            "notes": "Cadastro conferido",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["reviewer_public_id"] is not None

    detail = await client.get(
        f"/api/v1/participants/{user_id}", headers=auth_headers(admin_public_id)
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["cadastral_status"] == "VALIDATED"

    events = await client.get(
        f"/api/v1/participants/{user_id}/validations",
        headers=auth_headers(admin_public_id),
    )
    assert events.status_code == 200, events.text
    assert len(events.json()) == 1
    assert events.json()[0]["notes"] == "Cadastro conferido"


@pytest.mark.asyncio
async def test_mission_invitation_carries_purpose_mission_and_required_data(
    client, session_factory
):
    _, org_id, admin_public_id = await create_account(
        session_factory, "purpose.admin@example.com", "ADMIN"
    )
    async with session_factory() as session:
        mission = Mission(
            title="Missao Cadastro Global",
            mission_type=MissionType.VISTORIA,
            organization_id=uuid.UUID(org_id),
            city="Salvador",
            state="BA",
        )
        session.add(mission)
        await session.commit()
        mission_id = str(mission.id)

    created = await client.post(
        "/api/v1/invitations",
        headers=auth_headers(admin_public_id),
        json={
            "email": "purpose.participant@example.com",
            "journey_type": "PROFESSIONALS",
            "purpose": "MISSION_PARTICIPANT",
            "mission_id": mission_id,
            "required_data_categories": ["PROFILE", "DOCUMENTS", "QUALIFICATIONS"],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["purpose"] == "MISSION_PARTICIPANT"
    assert body["mission_id"] == mission_id
    assert body["required_data_categories"] == [
        "PROFILE",
        "DOCUMENTS",
        "QUALIFICATIONS",
    ]
    assert body["organization_id"] == org_id

    validated = await client.get(f"/api/v1/invitations/validate/{body['token']}")
    assert validated.status_code == 200, validated.text
    assert validated.json()["purpose"] == "MISSION_PARTICIPANT"
    assert validated.json()["mission_id"] == mission_id

    mismatched = await client.post(
        "/api/v1/invitations",
        headers=auth_headers(admin_public_id),
        json={
            "email": "purpose.invalid@example.com",
            "journey_type": "PROFESSIONALS",
            "purpose": "GLOBAL_REGISTRATION",
            "mission_id": mission_id,
        },
    )
    assert mismatched.status_code == 422


@pytest.mark.asyncio
async def test_invitation_registration_draft_is_encrypted_and_resumable(
    client, session_factory
):
    _, _, admin_public_id = await create_account(
        session_factory, "draft.admin@example.com", "ADMIN"
    )
    created = await client.post(
        "/api/v1/invitations",
        headers=auth_headers(admin_public_id),
        json={
            "email": "draft.participant@example.com",
            "journey_type": "PROFESSIONALS",
            "purpose": "GLOBAL_REGISTRATION",
            "required_data_categories": ["PROFILE", "BANK"],
        },
    )
    assert created.status_code == 201, created.text
    token = created.json()["token"]

    saved = await client.put(
        f"/api/v1/invitations/{token}/draft",
        json={
            "current_step": 3,
            "data": {
                "full_name": "Pessoa Rascunho",
                "cpf": "52998224725",
                "bank_account": {"bank": "001", "account": "998877"},
            },
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["current_step"] == 3
    assert saved.json()["status"] == "IN_PROGRESS"
    assert saved.json()["data"]["full_name"] == "Pessoa Rascunho"

    ciphertext = await _raw_row(
        session_factory,
        "SELECT data_encrypted FROM registration_drafts LIMIT 1",
        {},
    )
    assert ciphertext is not None
    assert "Pessoa Rascunho" not in ciphertext
    assert "998877" not in ciphertext

    resumed = await client.get(f"/api/v1/invitations/{token}/draft")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["data"]["bank_account"]["account"] == "998877"

    updated = await client.put(
        f"/api/v1/invitations/{token}/draft",
        json={"current_step": 4, "data": {"full_name": "Pessoa Atualizada"}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["current_step"] == 4
    assert updated.json()["data"]["full_name"] == "Pessoa Atualizada"

    missing = await client.get("/api/v1/invitations/token-inexistente/draft")
    assert missing.status_code == 404


def test_alembic_has_a_single_head_including_registration_migration():
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["b8d2f4a6c9e1"]
