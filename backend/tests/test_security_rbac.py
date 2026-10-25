"""
Automated unit & regression tests for OPERAN Security & RBAC.
Tests password hashing (Argon2), AES-256-GCM envelope encryption,
JWT token issuance and decoding, and UserContext RBAC isolation.
"""

import unittest
import uuid
import jwt
from datetime import datetime, timezone, timedelta

from app.security.hashing import get_password_hash, verify_password
from app.security.encryption import crypto_manager
from app.security.jwt import create_access_token, verify_token
from app.core.config import settings
from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.organization import Organization, OrganizationStatus
from app.models.membership import Membership, MembershipStatus
from app.models.network import Professional
from app.core.deps import UserContext


class TestSecurityAndHashing(unittest.TestCase):
    def test_argon2_password_hashing(self):
        password = "MinhaSenhaForte@2026"
        hashed = get_password_hash(password)
        self.assertNotEqual(password, hashed)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("SenhaErrada@123", hashed))

    def test_aes_gcm_encryption_and_tampering(self):
        secret_cpf = "123.456.789-00"
        encrypted_1 = crypto_manager.encrypt_data(secret_cpf)
        encrypted_2 = crypto_manager.encrypt_data(secret_cpf)
        # Nonce must be randomized: identical plaintext produces distinct ciphertexts
        self.assertNotEqual(encrypted_1, encrypted_2)

        # Correct decryption
        self.assertEqual(crypto_manager.decrypt_data(encrypted_1), secret_cpf)
        self.assertEqual(crypto_manager.decrypt_data(encrypted_2), secret_cpf)

        # Tampered ciphertext fallback
        tampered = encrypted_1[:-4] + "AAAA"
        self.assertEqual(crypto_manager.decrypt_data(tampered), "[Encrypted Data]")

    def test_jwt_token_creation_and_claims(self):
        public_id = "USR-TEST-001"
        token = create_access_token(data={"sub": public_id, "role": "ADMIN"})
        payload = verify_token(token)
        self.assertEqual(payload.get("sub"), public_id)
        self.assertEqual(payload.get("role"), "ADMIN")

    def test_jwt_token_expiration(self):
        public_id = "USR-EXP-001"
        expired_token = create_access_token(
            data={"sub": public_id},
            expires_delta=timedelta(seconds=-10),
        )
        with self.assertRaises(Exception):
            verify_token(expired_token)


class TestRbacAndTenantIsolation(unittest.TestCase):
    def setUp(self):
        self.user = User(
            id=uuid.uuid4(),
            public_id="USR-MOCK-1",
            email_hash="mockhash",
            email_encrypted="mockenc",
            password_hash="mockpass",
            status=UserStatus.ACTIVE,
        )

        self.org_a = Organization(
            id=uuid.uuid4(),
            public_id="ORG-A",
            name="Organizadora A",
            status=OrganizationStatus.ACTIVE,
        )

        self.org_b = Organization(
            id=uuid.uuid4(),
            public_id="ORG-B",
            name="Organizadora B",
            status=OrganizationStatus.ACTIVE,
        )

        self.admin_role = Role(
            id=uuid.uuid4(),
            name="ADMIN",
            is_system=True,
            description="Administrador Geral",
        )

        self.client_role = Role(
            id=uuid.uuid4(),
            name="CLIENT_ADMIN",
            is_system=False,
            description="Gestor Cliente",
        )

        self.participant_role = Role(
            id=uuid.uuid4(),
            name="PARTICIPANT",
            is_system=False,
            description="Colaborador Operacional",
        )

    def test_admin_context(self):
        membership = Membership(
            id=uuid.uuid4(),
            user_id=self.user.id,
            organization_id=self.org_a.id,
            role_id=self.admin_role.id,
            status=MembershipStatus.ACTIVE,
        )
        membership.role = self.admin_role
        membership.organization = self.org_a

        context = UserContext(user=self.user, memberships=[membership])
        self.assertTrue(context.is_admin)
        self.assertEqual(context.primary_role, "ADMIN")

    def test_client_context_and_tenant_scoping(self):
        membership = Membership(
            id=uuid.uuid4(),
            user_id=self.user.id,
            organization_id=self.org_a.id,
            role_id=self.client_role.id,
            status=MembershipStatus.ACTIVE,
        )
        membership.role = self.client_role
        membership.organization = self.org_a

        context = UserContext(user=self.user, memberships=[membership])
        self.assertFalse(context.is_admin)
        self.assertTrue(context.is_client)
        self.assertEqual(context.primary_role, "CLIENT")
        # Multi-tenant scoping: Org A is permitted, Org B is denied
        self.assertIn(self.org_a.id, context.client_organization_ids)
        self.assertNotIn(self.org_b.id, context.client_organization_ids)

    def test_participant_context(self):
        prof = Professional(
            id=uuid.uuid4(),
            user_id=self.user.id,
            full_name="Maria Silva",
            cpf_hash="cpfhash",
            cpf_encrypted="cpfenc",
            phone_encrypted="phoneenc",
            city="Brasília",
            state="DF",
            operational_radius_km=30,
            reputation_score=99.0,
        )

        context = UserContext(user=self.user, memberships=[], professional=prof)
        self.assertFalse(context.is_admin)
        self.assertFalse(context.is_client)
        self.assertTrue(context.is_participant)
        self.assertEqual(context.primary_role, "PARTICIPANT")
        self.assertEqual(len(context.client_organization_ids), 0)


if __name__ == "__main__":
    unittest.main()
