from __future__ import annotations

from typing import Any

from fastapi import Request

PHONE_AUTH_EVENT_TYPES = {"authorization_status", "authorizationstatus"}

_PHONE_AUTH_STATUS_KEYS = {
    "status",
    "state",
    "event",
    "type",
    "action",
    "detail",
    "message",
    "auth",
    "authorization",
    "connection",
    "session",
    "authstate",
    "accountstatus",
    "authstatus",
    "authorizationstatus",
    "connectionstatus",
}
_PHONE_AUTH_TRUE_MARKERS = (
    "authorized",
    "authorised",
    "authenticated",
    "auth_success",
    "authorization_success",
    "logged_in",
    "logged in",
    "connected",
    "online",
)
_PHONE_AUTH_FALSE_MARKERS = (
    "unauthorized",
    "unauthorised",
    "not_authorized",
    "not authorised",
    "not_authenticated",
    "not authenticated",
    "auth_required",
    "authorization_required",
    "logged_out",
    "logged out",
    "disconnected",
    "offline",
    "wait_qr",
    "need_qr",
    "qr_required",
    "qr_expired",
)
_PHONE_ONLINE_VALUES = {"online"}
_PHONE_OFFLINE_VALUES = {"offline"}
_PHONE_WEBHOOK_AUTH_HEADERS = (
    "auth",
    "x-wappi-auth",
    "x-webhook-auth",
    "authorization",
)


def _normalize_payload_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


def extract_phone_webhook_auth_secret(request: Request) -> str | None:
    for header_name in _PHONE_WEBHOOK_AUTH_HEADERS:
        raw_value = request.headers.get(header_name)
        if not isinstance(raw_value, str):
            continue
        normalized = raw_value.strip()
        if not normalized:
            continue
        if header_name == "authorization":
            parts = normalized.split(" ", 1)
            if len(parts) == 2 and parts[0].strip().lower() in {"bearer", "token"}:
                normalized = parts[1].strip()
        if normalized:
            return normalized
    return None


def coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return None


def _iter_json_nodes(payload: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    stack: list[Any] = [payload]
    visited = 0
    while stack and visited < 300:
        current = stack.pop()
        visited += 1
        if isinstance(current, dict):
            nodes.append(current)
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return nodes


def _extract_phone_auth_status_from_messages(
    payload: Any,
    *,
    expected_profile_id: str | None = None,
) -> bool | None:
    if not isinstance(payload, dict):
        return None

    raw_msgs = payload.get("messages")
    if isinstance(raw_msgs, dict):
        messages: list[Any] = [raw_msgs]
    elif isinstance(raw_msgs, list):
        messages = raw_msgs
    else:
        return None

    expected_profile = (expected_profile_id or "").strip().lower()
    for raw_message in messages:
        if not isinstance(raw_message, dict):
            continue

        wh_type_raw = raw_message.get("wh_type")
        wh_type = str(wh_type_raw).strip().lower() if wh_type_raw is not None else ""
        if wh_type and wh_type not in PHONE_AUTH_EVENT_TYPES:
            continue

        profile_raw = raw_message.get("profile_id")
        profile = str(profile_raw).strip().lower() if profile_raw is not None else ""
        if expected_profile and profile and profile != expected_profile:
            continue

        status_raw = raw_message.get("status")
        status_value = str(status_raw).strip().lower() if status_raw is not None else ""
        if status_value in _PHONE_ONLINE_VALUES:
            return True
        if status_value in _PHONE_OFFLINE_VALUES:
            return False

    return None


def _payload_has_only_non_auth_events(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    root_wh_type = str(payload.get("wh_type") or "").strip().lower()
    if root_wh_type:
        return root_wh_type not in PHONE_AUTH_EVENT_TYPES

    raw_messages = payload.get("messages")
    if isinstance(raw_messages, dict):
        messages: list[Any] = [raw_messages]
    elif isinstance(raw_messages, list):
        messages = raw_messages
    else:
        return False

    wh_types: set[str] = set()
    for raw_message in messages:
        if not isinstance(raw_message, dict):
            continue
        wh_type = str(raw_message.get("wh_type") or "").strip().lower()
        if wh_type:
            wh_types.add(wh_type)
    if not wh_types:
        return False
    return all(wh_type not in PHONE_AUTH_EVENT_TYPES for wh_type in wh_types)


def extract_phone_auth_state(
    payload: Any,
    *,
    expected_profile_id: str | None = None,
) -> bool | None:
    status_from_messages = _extract_phone_auth_status_from_messages(
        payload,
        expected_profile_id=expected_profile_id,
    )
    if status_from_messages is not None:
        return status_from_messages
    if _payload_has_only_non_auth_events(payload):
        return None

    status_fragments: list[str] = []
    qr_present = False

    for node in _iter_json_nodes(payload):
        for raw_key, raw_value in node.items():
            key = _normalize_payload_key(raw_key)
            if key in {"isauthorized", "authorized", "isauthenticated", "authenticated", "loggedin"}:
                bool_value = coerce_bool(raw_value)
                if bool_value is not None:
                    return bool_value

            if key in {"qr", "qrcode", "qrcodedata"} and isinstance(raw_value, str) and raw_value.strip():
                qr_present = True

            if key in _PHONE_AUTH_STATUS_KEYS:
                if isinstance(raw_value, str):
                    status_fragments.append(raw_value.lower())
                elif isinstance(raw_value, (int, float)):
                    status_fragments.append(str(raw_value))

    if status_fragments:
        combined = " | ".join(status_fragments)
        if any(marker in combined for marker in _PHONE_AUTH_FALSE_MARKERS):
            return False
        if any(marker in combined for marker in _PHONE_AUTH_TRUE_MARKERS):
            return True

    if qr_present:
        return False
    return None
