"""Regression tests for the P0 security and integrity fixes.

Each block covers one finding from the technical report. The tests use the
existing SQLite fixtures for business rules; PostgreSQL-specific behaviour
(concurrency and blind-index migration) lives in test_postgres_concurrency.py.
"""

import asyncio
import base64
import hashlib
import hmac
import os
import re
import time
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.future import select

import create_admin
from app.core.config import Settings, settings
from app.models.membership import Membership, MembershipStatus
from app.models.participant import AuditLog
from app.models.role import Role
from app.models.user import User, UserStatus
from app.security.blind_index import cpf_index, email_index
from app.security.hashing import verify_password
from app.services.login_limiter import LoginLimiter, RedisBackend
from conftest import auth_headers, create_account
from test_global_account import (
    TEST_AVATAR_BASE64,
    _accept_public,
    _create_invitation,
    _create_public_invitation,
)


def _accept_payload() -> dict:
    return {
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


async def _user_status(session_factory, user_id: str) -> UserStatus:
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(user_id))
        assert user is not None
        return user.status


# --------------------------------------------------------------------------- #
# Correction 1: an invitation must never reactivate a blocked account.
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_individual_invitation_activates_pending_user(client, session_factory):
    _, _, admin_pub = await create_account(
        session_factory, "admin.pending@example.com", "ADMIN"
    )
    email = "pending.individual@example.com"
    user_id, _, user_pub = await create_account(
        session_factory, email, "PARTICIPANT", user_status=UserStatus.PENDING
    )
    invitation = await _create_invitation(client, admin_pub, "PROFESSIONALS", email=email)

    response = await client.post(
        f"/api/v1/invitations/{invitation['token']}/accept",
        json=_accept_payload(),
        headers=auth_headers(user_pub),
    )

    assert response.status_code == 200, response.text
    assert await _user_status(session_factory, user_id) == UserStatus.ACTIVE


@pytest.mark.asyncio
async def test_individual_invitation_keeps_active_user_active(client, session_factory):
    _, _, admin_pub = await create_account(
        session_factory, "admin.active@example.com", "ADMIN"
    )
    email = "active.individual@example.com"
    user_id, _, user_pub = await create_account(
        session_factory, email, "PARTICIPANT", user_status=UserStatus.ACTIVE
    )
    invitation = await _create_invitation(client, admin_pub, "PROFESSIONALS", email=email)

    response = await client.post(
        f"/api/v1/invitations/{invitation['token']}/accept",
        json=_accept_payload(),
        headers=auth_headers(user_pub),
    )

    assert response.status_code == 200, response.text
    assert await _user_status(session_factory, user_id) == UserStatus.ACTIVE


@pytest.mark.asyncio
async def test_individual_invitation_does_not_reactivate_blocked_user(
    client, session_factory
):
    _, _, admin_pub = await create_account(
        session_factory, "admin.blocked@example.com", "ADMIN"
    )
    email = "blocked.individual@example.com"
    user_id, _, user_pub = await create_account(
        session_factory, email, "PARTICIPANT", user_status=UserStatus.BLOCKED
    )
    invitation = await _create_invitation(client, admin_pub, "PROFESSIONALS", email=email)

    response = await client.post(
        f"/api/v1/invitations/{invitation['token']}/accept",
        json=_accept_payload(),
        headers=auth_headers(user_pub),
    )

    assert response.status_code == 403, response.text
    assert "blocked" not in response.text.lower()
    assert await _user_status(session_factory, user_id) == UserStatus.BLOCKED


@pytest.mark.asyncio
async def test_public_invitation_activates_pending_user(client, session_factory):
    _, _, admin_pub = await create_account(
        session_factory, "admin.pending.public@example.com", "ADMIN"
    )
    email = "pending.public@example.com"
    user_id, _, user_pub = await create_account(
        session_factory, email, "PARTICIPANT", user_status=UserStatus.PENDING
    )
    link = await _create_public_invitation(client, admin_pub, "PROFESSIONALS", max_uses=2)

    response = await _accept_public(
        client, link["token"], email, headers=auth_headers(user_pub)
    )

    assert response.status_code == 200, response.text
    assert await _user_status(session_factory, user_id) == UserStatus.ACTIVE


@pytest.mark.asyncio
async def test_public_invitation_does_not_reactivate_blocked_user(
    client, session_factory
):
    _, _, admin_pub = await create_account(
        session_factory, "admin.blocked.public@example.com", "ADMIN"
    )
    email = "blocked.public@example.com"
    user_id, _, user_pub = await create_account(
        session_factory, email, "PARTICIPANT", user_status=UserStatus.BLOCKED
    )
    link = await _create_public_invitation(client, admin_pub, "PROFESSIONALS", max_uses=2)

    response = await _accept_public(
        client, link["token"], email, headers=auth_headers(user_pub)
    )

    assert response.status_code == 403, response.text
    assert "blocked" not in response.text.lower()
    assert await _user_status(session_factory, user_id) == UserStatus.BLOCKED


# --------------------------------------------------------------------------- #
# Correction 6: administrative bootstrap.
# --------------------------------------------------------------------------- #


def test_cli_rejects_password_as_argument():
    parser = create_admin.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["admin@example.com", "SecretPass@123"])


def test_password_prefers_environment(monkeypatch):
    monkeypatch.setenv(create_admin.PASSWORD_ENV, "EnvPassword@123")
    assert create_admin.resolve_password() == "EnvPassword@123"


def test_password_falls_back_to_hidden_prompt(monkeypatch):
    monkeypatch.delenv(create_admin.PASSWORD_ENV, raising=False)
    monkeypatch.setattr(
        create_admin.getpass, "getpass", lambda prompt: "TypedPassword@123"
    )
    assert create_admin.resolve_password() == "TypedPassword@123"


def test_short_password_is_rejected(monkeypatch):
    monkeypatch.setenv(create_admin.PASSWORD_ENV, "short")
    with pytest.raises(SystemExit):
        create_admin.resolve_password()


@pytest.mark.asyncio
async def test_bootstrap_does_not_reset_existing_password(
    session_factory, monkeypatch
):
    email = "bootstrap.existing@example.com"
    user_id, _, _ = await create_account(
        session_factory, email, "PARTICIPANT", password="OldPassword@123"
    )
    monkeypatch.setattr(create_admin, "async_session", session_factory)

    await create_admin.main(email, "NewPassword@123")

    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(user_id))
        assert user.status == UserStatus.ACTIVE
        assert verify_password("OldPassword@123", user.password_hash)
        assert not verify_password("NewPassword@123", user.password_hash)

        admin_role = (
            await session.execute(select(Role).where(Role.name == "ADMIN"))
        ).scalars().first()
        membership = (
            await session.execute(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.role_id == admin_role.id,
                    Membership.status == MembershipStatus.ACTIVE,
                )
            )
        ).scalars().first()
        assert membership is not None

        audit = (
            await session.execute(
                select(AuditLog).where(AuditLog.action == "admin.bootstrap")
            )
        ).scalars().first()
        assert audit is not None


@pytest.mark.asyncio
async def test_bootstrap_refuses_to_reactivate_blocked_user(
    session_factory, monkeypatch
):
    email = "bootstrap.blocked@example.com"
    user_id, _, _ = await create_account(
        session_factory, email, "PARTICIPANT", user_status=UserStatus.BLOCKED
    )
    monkeypatch.setattr(create_admin, "async_session", session_factory)

    with pytest.raises(SystemExit):
        await create_admin.main(email, "NewPassword@123")

    assert await _user_status(session_factory, user_id) == UserStatus.BLOCKED

    await create_admin.main(email, "NewPassword@123", activate_existing=True)
    assert await _user_status(session_factory, user_id) == UserStatus.ACTIVE


@pytest.mark.asyncio
async def test_admin_cannot_block_self(client, session_factory):
    admin_id, _, admin_pub = await create_account(
        session_factory, "self.block@example.com", "ADMIN"
    )

    response = await client.patch(
        f"/api/v1/users/{admin_id}/status",
        json={"status": "BLOCKED"},
        headers=auth_headers(admin_pub),
    )

    assert response.status_code == 400, response.text


@pytest.mark.asyncio
async def test_admin_can_block_another_admin(client, session_factory):
    _, _, admin_pub = await create_account(
        session_factory, "admin.caller@example.com", "ADMIN"
    )
    other_id, _, _ = await create_account(
        session_factory, "admin.other@example.com", "ADMIN"
    )

    response = await client.patch(
        f"/api/v1/users/{other_id}/status",
        json={"status": "BLOCKED"},
        headers=auth_headers(admin_pub),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "BLOCKED"


# --------------------------------------------------------------------------- #
# Correction 2: login throttling.
# --------------------------------------------------------------------------- #


async def _wrong_login(client, email):
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword@123"},
    )


@pytest.mark.asyncio
async def test_login_blocks_after_account_failures(
    client, session_factory, monkeypatch
):
    email = "throttle.account@example.com"
    await create_account(session_factory, email, password="CorrectPassword@123")
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ACCOUNT_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_IP_ATTEMPTS", 100)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_BASE_BLOCK_SECONDS", 60)

    for _ in range(3):
        response = await _wrong_login(client, email)
        assert response.status_code == 401, response.text

    blocked = await _wrong_login(client, email)
    assert blocked.status_code == 429, blocked.text
    assert "retry-after" in {key.lower() for key in blocked.headers}

    still_blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "CorrectPassword@123"},
    )
    assert still_blocked.status_code == 429


@pytest.mark.asyncio
async def test_login_block_expires(client, session_factory, monkeypatch):
    email = "throttle.recovery@example.com"
    await create_account(session_factory, email, password="CorrectPassword@123")
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ACCOUNT_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_IP_ATTEMPTS", 100)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_BASE_BLOCK_SECONDS", 1)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_MAX_BLOCK_SECONDS", 1)

    assert (await _wrong_login(client, email)).status_code == 401
    assert (await _wrong_login(client, email)).status_code == 401
    assert (await _wrong_login(client, email)).status_code == 429

    await asyncio.sleep(1.1)

    recovered = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "CorrectPassword@123"},
    )
    assert recovered.status_code == 200, recovered.text


@pytest.mark.asyncio
async def test_login_blocks_by_ip_across_accounts(client, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ACCOUNT_ATTEMPTS", 100)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_IP_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_BASE_BLOCK_SECONDS", 60)

    for index in range(3):
        response = await _wrong_login(client, f"unknown{index}@example.com")
        assert response.status_code == 401, response.text

    blocked = await _wrong_login(client, "another.unknown@example.com")
    assert blocked.status_code == 429, blocked.text


@pytest.mark.asyncio
async def test_login_errors_do_not_reveal_account_state(
    client, session_factory
):
    await create_account(
        session_factory,
        "hidden.pending@example.com",
        password="CorrectPassword@123",
        user_status=UserStatus.PENDING,
    )

    unknown = await _wrong_login(client, "does.not.exist@example.com")
    wrong_password = await _wrong_login(client, "hidden.pending@example.com")
    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json()["detail"] == wrong_password.json()["detail"]

    inactive = await client.post(
        "/api/v1/auth/login",
        json={"email": "hidden.pending@example.com", "password": "CorrectPassword@123"},
    )
    assert inactive.status_code == 403
    assert "pending" not in inactive.text.lower()
    assert "blocked" not in inactive.text.lower()


@pytest.mark.asyncio
async def test_successful_login_resets_account_counter(
    client, session_factory, monkeypatch
):
    email = "throttle.reset@example.com"
    await create_account(session_factory, email, password="CorrectPassword@123")
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ACCOUNT_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_IP_ATTEMPTS", 100)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_BASE_BLOCK_SECONDS", 60)

    assert (await _wrong_login(client, email)).status_code == 401
    assert (await _wrong_login(client, email)).status_code == 401

    success = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "CorrectPassword@123"},
    )
    assert success.status_code == 200

    assert (await _wrong_login(client, email)).status_code == 401
    assert (await _wrong_login(client, email)).status_code == 401
    assert (await _wrong_login(client, email)).status_code == 401
    assert (await _wrong_login(client, email)).status_code == 429


class _BrokenBackend:
    async def ttl(self, key):
        raise RuntimeError("cache down")


@pytest.mark.asyncio
async def test_limiter_fail_open_and_fail_closed(monkeypatch):
    limiter = LoginLimiter(_BrokenBackend())

    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_FAIL_OPEN", True)
    decision = await limiter.check(ip="203.0.113.1", account_hash="abc")
    assert decision.allowed is True

    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_FAIL_OPEN", False)
    decision = await limiter.check(ip="203.0.113.1", account_hash="abc")
    assert decision.allowed is False
    assert decision.retry_after == 60


@pytest.mark.asyncio
async def test_redis_backend_roundtrip(monkeypatch):
    url = os.environ.get("OPERAN_TEST_REDIS_URL")
    if not url:
        pytest.skip("OPERAN_TEST_REDIS_URL is not configured")
    limiter = LoginLimiter(RedisBackend(url))
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ACCOUNT_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_IP_ATTEMPTS", 100)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_BASE_BLOCK_SECONDS", 30)

    account_hash = f"test-{uuid.uuid4().hex}"
    try:
        assert (await limiter.check(ip="203.0.113.9", account_hash=account_hash)).allowed
        await limiter.record_failure(ip="203.0.113.9", account_hash=account_hash)
        decision = await limiter.check(ip="203.0.113.9", account_hash=account_hash)
        assert decision.allowed is False
        assert decision.retry_after > 0
    finally:
        await limiter.backend.delete(
            f"operan:login:account:{account_hash}:count",
            f"operan:login:account:{account_hash}:strikes",
            f"operan:login:account:{account_hash}:block",
            "operan:login:ip:203.0.113.9:count",
            "operan:login:ip:203.0.113.9:block",
        )
        await limiter.backend.close()


# --------------------------------------------------------------------------- #
# Correction 4: MFA limitation is documented and not promised anywhere.
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_login_has_no_mfa_challenge(client, session_factory):
    email = "mfa.limitation@example.com"
    await create_account(session_factory, email, password="CorrectPassword@123")

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "CorrectPassword@123"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("access_token")
    assert "mfa_required" not in body
    assert "mfa_token" not in body


def test_frontend_does_not_promise_mfa():
    frontend_src = Path(__file__).resolve().parents[2] / "frontend" / "src"
    if not frontend_src.is_dir():
        pytest.skip("frontend sources are not present")
    pattern = re.compile(r"mfa|2fa|multifator|two[\s-]?factor", re.IGNORECASE)
    type_only = re.compile(r"^\s*mfa_enabled\??\s*:\s*boolean\s*;?\s*$")
    offenders = []
    for path in frontend_src.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".html",
        }:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if pattern.search(line) and not type_only.match(line):
                offenders.append(f"{path.relative_to(frontend_src)}: {line.strip()}")
    assert not offenders, f"frontend promete MFA sem implementacao: {offenders}"


# --------------------------------------------------------------------------- #
# Correction 3: keyed blind indexes for PII.
# --------------------------------------------------------------------------- #


def test_blind_index_is_keyed_and_normalised(monkeypatch):
    email = "Person@Example.com"
    original = email_index(email)
    assert original == email_index(" person@example.com ")
    assert original != hashlib.sha256(email.lower().encode()).hexdigest()
    assert cpf_index("123.456.789-00") == cpf_index("12345678900")

    monkeypatch.setattr(
        settings, "PII_INDEX_KEY", "another-pii-index-key-0123456789abcdef0123456789"
    )
    assert email_index(email) != original


@pytest.mark.asyncio
async def test_registration_stores_keyed_hash(client, session_factory):
    email = "blind.index@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SenhaForte@2026"},
    )
    assert response.status_code == 201, response.text

    async with session_factory() as session:
        stored = (
            await session.execute(select(User).where(User.email_hash == email_index(email)))
        ).scalars().first()
        assert stored is not None
        assert stored.email_hash != hashlib.sha256(email.encode()).hexdigest()


def _load_blind_index_migration():
    import importlib.util

    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "b8d2f4a6c9e1_blind_index_pii_hmac.py"
    )
    spec = importlib.util.spec_from_file_location("blind_index_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_recomputes_hashes_and_clears_unreadable(monkeypatch):
    from sqlalchemy import create_engine, text

    from app.security.encryption import crypto_manager

    monkeypatch.setenv("PII_INDEX_KEY", settings.PII_INDEX_KEY)
    module = _load_blind_index_migration()
    engine = create_engine("sqlite://")
    with engine.begin() as bind:
        bind.execute(
            text(
                "CREATE TABLE users (id VARCHAR PRIMARY KEY, email_encrypted VARCHAR, "
                "email_hash VARCHAR)"
            )
        )
        readable = crypto_manager.encrypt_data("readable@example.com")
        bind.execute(
            text("INSERT INTO users VALUES ('1', :v, 'legacy')"), {"v": readable}
        )
        bind.execute(
            text("INSERT INTO users VALUES ('2', :v, 'legacy')"),
            {"v": "not-encrypted"},
        )

        module._recompute(
            bind,
            table="users",
            select_columns="email_encrypted",
            updates=[("email_hash", "email_encrypted", module._email_index)],
            key=b"k" * 32,
            tolerate_decrypt_errors=True,
        )
        rows = dict(
            bind.execute(text("SELECT id, email_hash FROM users")).fetchall()
        )
        assert rows["1"] == hmac.new(
            b"k" * 32, b"readable@example.com", hashlib.sha256
        ).hexdigest()
        assert rows["2"] is None


# --------------------------------------------------------------------------- #
# Fase 1.1: configuration and availability hardening.
# --------------------------------------------------------------------------- #


def test_pii_index_key_must_differ_from_other_secrets():
    base = {
        "SECRET_KEY": "s" * 40,
        "CRYPTO_KEY": base64.b64encode(b"c" * 32).decode(),
    }
    with pytest.raises(ValidationError):
        Settings(PII_INDEX_KEY=base["SECRET_KEY"], **base)
    with pytest.raises(ValidationError):
        Settings(PII_INDEX_KEY=base["CRYPTO_KEY"], **base)


@pytest.mark.asyncio
async def test_unreachable_redis_fails_within_bounded_time(monkeypatch):
    backend = RedisBackend("redis://127.0.0.1:6399/0")
    limiter = LoginLimiter(backend)
    try:
        monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_FAIL_OPEN", True)
        started = time.monotonic()
        decision = await limiter.check(ip="203.0.113.50", account_hash="redis-down")
        elapsed = time.monotonic() - started
        assert decision.allowed is True
        assert elapsed < 3

        monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_FAIL_OPEN", False)
        decision = await limiter.check(ip="203.0.113.50", account_hash="redis-down")
        assert decision.allowed is False
    finally:
        await backend.close()
