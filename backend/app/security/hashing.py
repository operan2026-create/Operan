from passlib.context import CryptContext

# Configuring Argon2id as recommended by OWASP ASVS 5.0
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generates an Argon2id hash for the given password."""
    return pwd_context.hash(password)
