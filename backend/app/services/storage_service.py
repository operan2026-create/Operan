import hashlib
import uuid
from pathlib import Path

from app.core.config import settings
from app.security.encryption import crypto_manager

ENCRYPTED_FILE_MAGIC = b"OPERAN-ENC-1\x00"


def storage_root() -> Path:
    root = Path(settings.DOCUMENT_STORAGE_DIR)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(storage_key: str) -> Path:
    root = storage_root().resolve()
    candidate = (root / storage_key).resolve()
    if root not in candidate.parents:
        raise ValueError("Caminho de documento invalido.")
    return candidate


def save_document(participant_user_id: uuid.UUID, content: bytes, extension: str) -> tuple[str, str]:
    key = f"{participant_user_id}/{uuid.uuid4().hex}.{extension}"
    path = _safe_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = ENCRYPTED_FILE_MAGIC + crypto_manager.encrypt_bytes(content)
    path.write_bytes(encrypted)
    return key, hashlib.sha256(content).hexdigest()


def document_path(storage_key: str) -> Path:
    path = _safe_path(storage_key)
    if not path.is_file():
        raise FileNotFoundError("Documento nao encontrado no storage.")
    return path


def read_document(storage_key: str) -> bytes:
    payload = document_path(storage_key).read_bytes()
    if payload.startswith(ENCRYPTED_FILE_MAGIC):
        return crypto_manager.decrypt_bytes(payload[len(ENCRYPTED_FILE_MAGIC) :])
    return payload


def delete_document(storage_key: str) -> None:
    try:
        _safe_path(storage_key).unlink(missing_ok=True)
    except ValueError:
        return
