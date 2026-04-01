from __future__ import annotations

from typing import Any

from app.services.credentials import ENCRYPTED_MARKER, decrypt_config, encrypt_config

SENSITIVE_CLIENT_FIELDS = (
    "passportData",
    "medicalClientData",
    "address",
    "email",
    "firstname",
    "lastname",
    "patronymic",
    "phone",
    "additionalPhone",
    "birthDate",
)


def split_client_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    safe_payload = dict(payload)
    pii_payload: dict[str, Any] = {}

    for field in SENSITIVE_CLIENT_FIELDS:
        if field not in safe_payload:
            continue
        value = safe_payload.pop(field)
        if value is None:
            continue
        pii_payload[field] = value

    return safe_payload, pii_payload


def encrypt_client_pii(pii_payload: dict[str, Any]) -> dict[str, Any] | None:
    if not pii_payload:
        return None
    encrypted = encrypt_config(pii_payload)
    if not (isinstance(encrypted, dict) and encrypted.get(ENCRYPTED_MARKER)):
        raise ValueError("CREDENTIALS_ENCRYPTION_KEY is required for SQNS client PII encryption")
    return encrypted


def decrypt_client_pii(pii_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not pii_payload:
        return {}
    if not isinstance(pii_payload, dict):
        raise ValueError("SQNS client pii payload has invalid format")
    if pii_payload.get(ENCRYPTED_MARKER):
        decrypted = decrypt_config(pii_payload)
        if not isinstance(decrypted, dict):
            raise ValueError("SQNS client pii payload is invalid after decrypt")
        return decrypted
    # Обратная совместимость для старых записей (если когда-то были сохранены как plain JSON).
    return pii_payload


def merge_client_payload(
    safe_payload: dict[str, Any] | None,
    pii_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(safe_payload or {})
    decrypted_pii = decrypt_client_pii(pii_payload)
    for field in SENSITIVE_CLIENT_FIELDS:
        if field in decrypted_pii:
            merged[field] = decrypted_pii[field]
    return merged
