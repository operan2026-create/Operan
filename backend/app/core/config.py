import base64

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

# Valores que jamais devem ser aceitos como segredo de producao. A aplicacao
# deve falhar na inicializacao em vez de operar com uma chave publica.
_INSECURE_SECRET_MARKERS = (
    "insecure",
    "change_me",
    "change-me",
    "changeme",
    "replace",
    "example",
    "development",
    "secret_key",
)


class Settings(BaseSettings):
    PROJECT_NAME: str = "OPERAN API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Security - must be provided explicitly via environment / .env
    SECRET_KEY: str
    CRYPTO_KEY: str
    # Dedicated key for deterministic blind indexes of PII (e-mail, CPF, RG,
    # CNPJ). It must live outside the database and must never be the JWT secret.
    PII_INDEX_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://operan_user:operan_password@localhost:5432/operan_db"
    SQL_ECHO: bool = False

    # Login rate limiting (Redis optional; in-memory fallback when absent)
    REDIS_URL: Optional[str] = None
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300
    LOGIN_RATE_LIMIT_IP_ATTEMPTS: int = 20
    LOGIN_RATE_LIMIT_ACCOUNT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_BASE_BLOCK_SECONDS: int = 60
    LOGIN_RATE_LIMIT_MAX_BLOCK_SECONDS: int = 900
    LOGIN_RATE_LIMIT_STRIKES_TTL_SECONDS: int = 3600
    LOGIN_RATE_LIMIT_FAIL_OPEN: bool = True
    TRUST_PROXY_HEADERS: bool = False

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Private document storage (never served as static files)
    DOCUMENT_STORAGE_DIR: str = "storage/participant-documents"
    MAX_DOCUMENT_SIZE_BYTES: int = 10 * 1024 * 1024
    MAX_AVATAR_SIZE_BYTES: int = 5 * 1024 * 1024
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters long. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        lowered = normalized.lower()
        if any(marker in lowered for marker in _INSECURE_SECRET_MARKERS):
            raise ValueError(
                "SECRET_KEY uses an insecure placeholder value. Provide a real random secret."
            )
        return normalized

    @field_validator("CRYPTO_KEY")
    @classmethod
    def validate_crypto_key(cls, value: str) -> str:
        try:
            raw = base64.b64decode(value, validate=True)
        except Exception as exc:  # noqa: BLE001 - surface a clear configuration error
            raise ValueError("CRYPTO_KEY must be a base64-encoded 32-byte key.") from exc
        if len(raw) != 32:
            raise ValueError("CRYPTO_KEY must decode to exactly 32 bytes (AES-256).")
        return value

    @field_validator("PII_INDEX_KEY")
    @classmethod
    def validate_pii_index_key(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 32:
            raise ValueError(
                "PII_INDEX_KEY must be at least 32 characters long. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        lowered = normalized.lower()
        if any(marker in lowered for marker in _INSECURE_SECRET_MARKERS):
            raise ValueError(
                "PII_INDEX_KEY uses an insecure placeholder value. Provide a real random secret."
            )
        return normalized

    @field_validator("ALGORITHM")
    @classmethod
    def validate_algorithm(cls, value: str) -> str:
        if value not in {"HS256", "HS384", "HS512"}:
            raise ValueError("ALGORITHM must be one of HS256, HS384 or HS512.")
        return value

    @model_validator(mode="after")
    def validate_key_separation(self) -> "Settings":
        if self.PII_INDEX_KEY == self.SECRET_KEY:
            raise ValueError("PII_INDEX_KEY must be different from SECRET_KEY.")
        if self.PII_INDEX_KEY == self.CRYPTO_KEY:
            raise ValueError("PII_INDEX_KEY must be different from CRYPTO_KEY.")
        return self


settings = Settings()
