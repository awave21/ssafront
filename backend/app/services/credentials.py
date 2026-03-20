from __future__ import annotations

from functools import lru_cache
import json
from typing import Any

import structlog
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

ENCRYPTED_MARKER = "__encrypted__"
ENCRYPTED_PAYLOAD = "payload"


@lru_cache
def _get_fernet() -> Fernet | None:
    settings = get_settings()
    key = settings.credentials_encryption_key
    if not key:
        logger.warning("credentials_encryption_key_missing")
        return None
    return Fernet(key)


def _is_encrypted(config: dict[str, Any]) -> bool:
    return bool(config.get(ENCRYPTED_MARKER)) and isinstance(config.get(ENCRYPTED_PAYLOAD), str)


def encrypt_config(config: dict[str, Any]) -> dict[str, Any]:
    if not config:
        return config
    fernet = _get_fernet()
    if fernet is None:
        return config
    payload = json.dumps(config).encode()
    token = fernet.encrypt(payload).decode()
    return {ENCRYPTED_MARKER: True, ENCRYPTED_PAYLOAD: token}


def decrypt_config(config: dict[str, Any]) -> dict[str, Any]:
    if not config:
        return config
    if not _is_encrypted(config):
        return config
    fernet = _get_fernet()
    if fernet is None:
        raise ValueError("Credentials encryption key is missing")
    token = config.get(ENCRYPTED_PAYLOAD, "")
    try:
        payload = fernet.decrypt(token.encode())
    except InvalidToken as exc:
        raise ValueError("Invalid credentials payload") from exc
    parsed = json.loads(payload.decode())
    if isinstance(parsed, dict):
        return parsed
    raise ValueError("Decrypted credentials payload is invalid")


def mask_config(config: dict[str, Any]) -> dict[str, Any]:
    def _mask(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: _mask(val) for key, val in value.items()}
        if isinstance(value, list):
            return [_mask(item) for item in value]
        return "***"

    if not config:
        return config
    return _mask(config)
