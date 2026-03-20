from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.webhooks_utils import mask_headers
from app.db.models.channel import Channel
from app.db.session import get_db

logger = structlog.get_logger()
wappi_webhook_logger = structlog.get_logger("webhooks.wappi")

router = APIRouter()

_PHONE_CHANNEL_TYPES = {"telegram_phone", "whatsapp", "max"}
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
    "pending",
    "wait_qr",
    "need_qr",
    "qr_required",
    "qr_expired",
)
_PHONE_AUTH_EVENT_TYPES = {"authorization_status", "authorizationstatus"}
_PHONE_ONLINE_VALUES = {"online"}
_PHONE_OFFLINE_VALUES = {"offline"}


def _normalize_payload_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _coerce_bool(value: Any) -> bool | None:
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

    messages = payload.get("messages")
    if not isinstance(messages, list):
        return None

    expected_profile = (expected_profile_id or "").strip().lower()
    for raw_message in messages:
        if not isinstance(raw_message, dict):
            continue

        wh_type_raw = raw_message.get("wh_type")
        wh_type = str(wh_type_raw).strip().lower() if wh_type_raw is not None else ""
        if wh_type and wh_type not in _PHONE_AUTH_EVENT_TYPES:
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


def _extract_phone_auth_state(
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

    status_fragments: list[str] = []
    qr_present = False

    for node in _iter_json_nodes(payload):
        for raw_key, raw_value in node.items():
            key = _normalize_payload_key(raw_key)
            if key in {"isauthorized", "authorized", "isauthenticated", "authenticated", "loggedin"}:
                bool_value = _coerce_bool(raw_value)
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


@router.post("/webhooks/channels/phone/{channel_id}")
async def phone_channel_webhook(
    channel_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    stmt = select(Channel).where(
        Channel.id == channel_id,
        Channel.is_deleted.is_(False),
    )
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    if channel.type not in _PHONE_CHANNEL_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Channel is not phone type")

    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8", errors="replace")
    parsed_json: dict[str, Any] | list[Any] | None = None
    if raw_body:
        try:
            parsed_json = json.loads(raw_body)
        except Exception:
            parsed_json = None

    payload_for_state = parsed_json if isinstance(parsed_json, (dict, list)) else None
    auth_state = (
        _extract_phone_auth_state(
            payload_for_state,
            expected_profile_id=channel.wappi_profile_id,
        )
        if payload_for_state is not None
        else None
    )

    previous_auth_state = bool(channel.phone_is_authorized)
    changed_auth_state = False
    if auth_state is not None and previous_auth_state != auth_state:
        channel.phone_is_authorized = auth_state
        await db.commit()
        changed_auth_state = True

    log_payload: dict[str, Any] = {
        "channel_id": str(channel.id),
        "channel_type": channel.type,
        "method": request.method,
        "path": str(request.url.path),
        "query_params": dict(request.query_params),
        "headers": mask_headers(dict(request.headers)),
        "body_raw": raw_text,
        "body_json": parsed_json,
        "client_ip": request.client.host if request.client else "unknown",
        "detected_auth_state": auth_state,
        "previous_auth_state": previous_auth_state,
        "changed_auth_state": changed_auth_state,
    }
    wappi_webhook_logger.info("phone_channel_webhook_incoming", **log_payload)
    logger.info("phone_channel_webhook_received", **log_payload)

    return {"ok": True}
