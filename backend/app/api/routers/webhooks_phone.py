from __future__ import annotations

import json
import secrets
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.webhooks_inbound_agent import (
    append_wappi_linked_account_message,
    process_webhook_inbound_agent_message,
)
from app.api.routers.webhooks_utils import mask_headers, sanitize_agent_reply_text
from app.db.models.agent import Agent
from app.db.models.channel import AgentChannel, Channel
from app.db.models.run import Run
from app.db.models.session_message import SessionMessage
from app.db.session import get_db
from app.services.agent_user_state import is_agent_user_disabled
from app.services.dialog_state import is_dialog_active, is_manager_paused
from app.services.wappi import (
    WappiClientError,
    build_wappi_client,
    resolve_wappi_async_timeout_range,
    resolve_wappi_max_bot_id,
)
from app.services.wappi.binding import ChannelProfileConfigError
from app.utils.broadcast import broadcaster

logger = structlog.get_logger()
wappi_webhook_logger = structlog.get_logger("webhooks.wappi")
_WAPPI_PLATFORM_WEBHOOK_LOGGERS = {
    "telegram_phone": structlog.get_logger("webhooks.wappi.telegram"),
    "whatsapp": structlog.get_logger("webhooks.wappi.whatsapp"),
    "max": structlog.get_logger("webhooks.wappi.max"),
}

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
    "wait_qr",
    "need_qr",
    "qr_required",
    "qr_expired",
)
_PHONE_AUTH_EVENT_TYPES = {"authorization_status", "authorizationstatus"}
_PHONE_ONLINE_VALUES = {"online"}
_PHONE_OFFLINE_VALUES = {"offline"}
_PHONE_WEBHOOK_AUTH_HEADERS = (
    "auth",
    "x-wappi-auth",
    "x-webhook-auth",
    "authorization",
)
_WAPPI_TELEGRAM_TEXT_EVENT_TYPES = {"incoming_message", "outgoing_message_phone"}
_WAPPI_WHATSAPP_TEXT_EVENT_TYPES = {"incoming_message", "outgoing_message_phone"}
_WAPPI_MAX_TEXT_EVENT_TYPES = {
    "incoming_message",
    "outgoing_message_phone",
    "outgoing_message",
    "out_message",
    "message",
    "new_message",
    "dialog_message",
}
_WAPPI_DELIVERY_EVENT_TYPES = {"delivery_status"}
_WAPPI_TEXT_MESSAGE_TYPES = {"text", "chat", "message", "plain"}
_WAPPI_IGNORED_NON_TEXT_TYPES = {"image", "document", "video", "ptt", "audio"}
_WAPPI_DELIVERY_STATUS_RANK: dict[str, int] = {
    "sent": 1,
    "delivered": 2,
    "read": 3,
}
_WAPPI_DELIVERY_STATUS_ALIAS: dict[str, str] = {
    "sent": "sent",
    "success": "sent",
    "ok": "sent",
    "delivered": "delivered",
    "delivery": "delivered",
    "received": "delivered",
    "read": "read",
    "seen": "read",
    "displayed": "read",
}


def _normalize_payload_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _extract_phone_webhook_auth_secret(request: Request) -> str | None:
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


def _payload_has_only_non_auth_events(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    root_wh_type = str(payload.get("wh_type") or "").strip().lower()
    if root_wh_type:
        return root_wh_type not in _PHONE_AUTH_EVENT_TYPES

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
    return all(wh_type not in _PHONE_AUTH_EVENT_TYPES for wh_type in wh_types)


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
    if _payload_has_only_non_auth_events(payload):
        return None

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


_PHONE_CHANNEL_LABELS: dict[str, str] = {
    "telegram_phone": "Telegram номер",
    "whatsapp": "WhatsApp",
    "max": "MAX",
}


def _contact_sender_display_label(channel_type: str) -> str:
    channel_label = _PHONE_CHANNEL_LABELS.get(channel_type, channel_type.replace("_", " ").title())
    return f"Клиент ({channel_label})"


def _operator_sender_display_label(channel_type: str) -> str:
    channel_label = _PHONE_CHANNEL_LABELS.get(channel_type, channel_type.replace("_", " ").title())
    return f"Оператор ({channel_label})"


def _wappi_is_from_linked_account(msg: dict[str, Any]) -> bool:
    """Сообщение отправлено с привязанного аккаунта (личный клиент / приложение), а не получено от контакта."""
    for key in ("from_me", "fromMe", "outgoing", "is_me", "isMe", "fromSelf", "self"):
        if key not in msg:
            continue
        b = _coerce_bool(msg.get(key))
        if b is True:
            return True
    return False


def _wappi_likely_api_automated_send(msg: dict[str, Any]) -> bool:
    """
    Эхо отправки через API (ответ агента) — не дублировать в чате.
    Не используем широкие значения вроде \"sync\"/\"wappi\" в source: ими MAX может помечать и ручные отправки.
    """
    b = _coerce_bool(msg.get("from_api") or msg.get("fromApi"))
    if b is True:
        return True
    ts = str(
        msg.get("type_send")
        or msg.get("typeSend")
        or msg.get("send_type")
        or msg.get("sendType")
        or ""
    ).strip().lower()
    if ts in {"api", "automation"}:
        return True
    src = str(
        msg.get("source")
        or msg.get("origin")
        or msg.get("send_source")
        or msg.get("message_source")
        or msg.get("sendSource")
        or ""
    ).strip().lower()
    if src in {"api", "automation", "bot"}:
        return True
    return False


def _wappi_message_type(msg: dict[str, Any]) -> str:
    return str(
        msg.get("type")
        or msg.get("message_type")
        or msg.get("msg_type")
        or msg.get("media_type")
        or ""
    ).strip().lower()


def _wappi_is_text_message(msg: dict[str, Any]) -> bool:
    msg_type = _wappi_message_type(msg)
    if not msg_type:
        return _wappi_extract_text_body(msg) is not None
    if msg_type in _WAPPI_IGNORED_NON_TEXT_TYPES:
        return False
    return msg_type in _WAPPI_TEXT_MESSAGE_TYPES


def _wappi_is_private_chat(msg: dict[str, Any], *, channel_type: str) -> bool:
    """
    Унифицированный фильтр личного чата:
    - отсекает группы/каналы;
    - для WhatsApp отсекает group-id (*@g.us);
    - для Telegram-number отсекает peer с '-' (группы/каналы).
    """
    ct = str(msg.get("chat_type") or "").strip().lower()
    if ct in ("group", "supergroup", "channel", "chat", "megagroup"):
        return False
    if ct in ("private", "user", "dialog", "direct", "dm", "personal"):
        return True

    peer_candidates = [
        str(msg.get("chatId") or "").strip(),
        str(msg.get("chat_id") or "").strip(),
        str(msg.get("to") or "").strip(),
        str(msg.get("from") or "").strip(),
    ]
    peer_candidates = [peer for peer in peer_candidates if peer]
    if not peer_candidates:
        return False

    if channel_type == "whatsapp":
        lowered_candidates = [peer.lower() for peer in peer_candidates]
        if any(peer.endswith("@g.us") for peer in lowered_candidates):
            return False
        if any(peer.endswith("@s.whatsapp.net") for peer in lowered_candidates):
            return True

    if channel_type == "telegram_phone":
        if any(peer.startswith("-") for peer in peer_candidates):
            return False

    return True


def _wappi_platform_is_max(platform_raw: Any) -> bool:
    s = str(platform_raw or "").strip().lower()
    if not s:
        return False
    if s == "max":
        return True
    if s.startswith("max_") or s.startswith("max-"):
        return True
    return s in {"maxmessenger", "max_messenger", "maxapi", "max_api"}


def _wappi_coerce_message_dicts(parsed_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Wappi: messages — массив, один объект или событие в корне JSON."""
    raw = parsed_json.get("messages")
    if isinstance(raw, list):
        return [m for m in raw if isinstance(m, dict)]
    if isinstance(raw, dict):
        return [raw]
    looks_like_message_event = parsed_json.get("wh_type") is not None or (
        parsed_json.get("body") is not None
        and (
            parsed_json.get("chatId") is not None
            or parsed_json.get("chat_id") is not None
            or parsed_json.get("from") is not None
            or parsed_json.get("to") is not None
        )
    )
    if looks_like_message_event:
        return [parsed_json]
    return []


def _wappi_extract_text_body(raw_msg: dict[str, Any]) -> str | None:
    """Текст входящего сообщения: body строка или вложенный объект."""
    body = raw_msg.get("body")
    if isinstance(body, str) and body.strip():
        return body.strip()
    if isinstance(body, dict):
        nested = body.get("text") or body.get("content") or body.get("message")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    for key in ("text", "content", "message"):
        val = raw_msg.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _wappi_max_wh_type_is_chat_message(wh_type: str) -> bool:
    """
    Wappi MAX: входящие — incoming_message; сообщения, отправленные с привязанного аккаунта в клиенте,
    часто приходят как outgoing_message / out_message (см. логи webhooks.wappi body_json).
    """
    w = (wh_type or "").strip().lower()
    return w in _WAPPI_MAX_TEXT_EVENT_TYPES


def _wappi_telegram_reply_recipient(msg: dict[str, Any]) -> str | None:
    """Идентификатор чата для ответа (tapi sync message send)."""
    for key in ("chatId", "chat_id", "to"):
        raw = msg.get(key)
        if raw is None:
            continue
        s = str(raw).strip()
        if s:
            return s
    return None


def _wappi_whatsapp_reply_recipient(msg: dict[str, Any]) -> str | None:
    for key in ("chatId", "chat_id", "to", "recipient", "phone", "from"):
        raw = msg.get(key)
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            return value
    return None


def _wappi_whatsapp_send_recipient(session_peer: str) -> str:
    normalized_peer = (session_peer or "").strip()
    if not normalized_peer:
        return ""
    lowered = normalized_peer.lower()
    if lowered.endswith("@s.whatsapp.net") or lowered.endswith("@c.us"):
        normalized_peer = normalized_peer.split("@", 1)[0]
    return "".join(ch for ch in normalized_peer if ch.isdigit()) or normalized_peer


def _wappi_extract_phone_digits(value: Any) -> str | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    peer_part = raw_value.split("@", 1)[0] if "@" in raw_value else raw_value
    digits = "".join(ch for ch in peer_part if ch.isdigit())
    if len(digits) < 10 or len(digits) > 15:
        return None
    return digits


def _wappi_resolve_contact_phone(msg: dict[str, Any]) -> str | None:
    explicit_contact = _wappi_extract_phone_digits(msg.get("contact_phone") or msg.get("contactPhone"))
    if explicit_contact:
        return explicit_contact

    linked_account_message = _wappi_is_from_linked_account(msg) or (
        str(msg.get("wh_type") or "").strip().lower() == "outgoing_message_phone"
    )
    primary_key = "to" if linked_account_message else "from"
    fallback_keys = (
        primary_key,
        "recipient",
        "phone",
        "chatId",
        "chat_id",
    )
    for key in fallback_keys:
        candidate_phone = _wappi_extract_phone_digits(msg.get(key))
        if candidate_phone:
            return candidate_phone
    return None


def _wappi_base_phone_user_info(
    msg: dict[str, Any],
    *,
    session_peer: str,
    channel: Channel,
    platform_name: str,
) -> dict[str, Any]:
    from_id = str(msg.get("from") or "").strip() or session_peer
    channel_label = _PHONE_CHANNEL_LABELS.get(channel.type, channel.type.replace("_", " ").title())
    info: dict[str, Any] = {
        "platform": platform_name,
        "platform_id": from_id,
        "integration_channel_type": channel.type,
        "integration_channel_label": channel_label,
        "wappi_direction": "in",
        "message_sender_kind": "contact",
        "sender_display_label": _contact_sender_display_label(channel.type),
    }
    contact_phone = _wappi_resolve_contact_phone(msg)
    if contact_phone:
        info["contact_phone"] = contact_phone
    if isinstance(msg.get("username"), str) and msg["username"].strip():
        info["username"] = msg["username"].strip()
    if isinstance(msg.get("senderName"), str) and msg["senderName"].strip():
        info["first_name"] = msg["senderName"].strip()
    if isinstance(msg.get("senderLastName"), str) and msg["senderLastName"].strip():
        info["last_name"] = msg["senderLastName"].strip()
    return info


def _wappi_telegram_phone_user_info(
    msg: dict[str, Any],
    *,
    chat_id_str: str,
    channel: Channel,
) -> dict[str, Any]:
    return _wappi_base_phone_user_info(
        msg,
        session_peer=chat_id_str,
        channel=channel,
        platform_name="telegram_phone",
    )


def _wappi_phone_operator_user_info(base_info: dict[str, Any], *, channel_type: str) -> dict[str, Any]:
    info = {**base_info}
    info["wappi_direction"] = "out"
    info["message_sender_kind"] = "wappi_operator"
    info["sender_display_label"] = _operator_sender_display_label(channel_type)
    return info


def _wappi_normalize_delivery_status(raw_status: Any) -> str | None:
    value = str(raw_status or "").strip().lower()
    if not value:
        return None
    return _WAPPI_DELIVERY_STATUS_ALIAS.get(value)


def _wappi_extract_provider_message_id(msg: dict[str, Any]) -> str | None:
    raw = msg.get("id") or msg.get("message_id") or msg.get("messageId")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _wappi_extract_provider_task_id(msg: dict[str, Any]) -> str | None:
    raw = msg.get("task_id") or msg.get("taskId") or msg.get("queue_task_id") or msg.get("queueTaskId")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _wappi_extract_provider_uuid(msg: dict[str, Any]) -> str | None:
    raw = msg.get("uuid")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _wappi_delivery_status_rank(status_value: str | None) -> int:
    if not status_value:
        return 0
    return _WAPPI_DELIVERY_STATUS_RANK.get(status_value, 0)


def _wappi_extract_manager_text(message_payload: dict[str, Any]) -> str:
    parts = message_payload.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if not isinstance(part, dict):
                continue
            part_kind = str(part.get("part_kind") or "").strip().lower()
            if part_kind not in {"manager-message", "manager_message", "manager", "text", "user-prompt"}:
                continue
            content = str(part.get("content") or "").strip()
            if content:
                return content
    fallback = str(message_payload.get("content") or "").strip()
    return fallback


def _wappi_outbound_channel_type_from_payload(message_payload: dict[str, Any]) -> str:
    direct_type = str(message_payload.get("outbound_channel_type") or "").strip().lower()
    if direct_type:
        return direct_type
    user_info = message_payload.get("user_info")
    if isinstance(user_info, dict):
        nested_type = str(user_info.get("integration_channel_type") or "").strip().lower()
        if nested_type:
            return nested_type
    return ""


def _wappi_message_is_manager(message_payload: dict[str, Any]) -> bool:
    role = str(message_payload.get("role") or "").strip().lower()
    if role == "manager":
        return True
    user_info = message_payload.get("user_info")
    if isinstance(user_info, dict):
        sender_kind = str(user_info.get("message_sender_kind") or "").strip().lower()
        if sender_kind in {"manager", "wappi_operator"}:
            return True
    return False


def _wappi_message_has_failed_status(message_payload: dict[str, Any]) -> bool:
    raw_status = str(message_payload.get("status") or "").strip().lower()
    return raw_status == "failed"


async def _wappi_find_outgoing_message_candidate(
    db: AsyncSession,
    *,
    agent_id: UUID,
    agent: Agent,
    session_id: str,
    channel_type: str,
    provider_message_id: str | None = None,
    provider_task_id: str | None = None,
    provider_uuid: str | None = None,
    text_hint: str | None = None,
) -> SessionMessage | None:
    exact_lookups: list[tuple[str, str]] = []
    if provider_message_id:
        exact_lookups.append(("provider_message_id", provider_message_id))
    if provider_task_id:
        exact_lookups.append(("provider_task_id", provider_task_id))
    if provider_uuid:
        exact_lookups.append(("provider_uuid", provider_uuid))

    for metadata_key, metadata_value in exact_lookups:
        stmt = (
            select(SessionMessage)
            .join(Run, Run.id == SessionMessage.run_id)
            .where(
                SessionMessage.tenant_id == agent.tenant_id,
                SessionMessage.session_id == session_id,
                Run.agent_id == agent_id,
                SessionMessage.message[metadata_key].astext == metadata_value,
            )
            .order_by(SessionMessage.message_index.desc())
            .limit(1)
        )
        message = (await db.execute(stmt)).scalar_one_or_none()
        if message is not None:
            return message

    if not text_hint:
        return None

    stmt = (
        select(SessionMessage)
        .join(Run, Run.id == SessionMessage.run_id)
        .where(
            SessionMessage.tenant_id == agent.tenant_id,
            SessionMessage.session_id == session_id,
            Run.agent_id == agent_id,
        )
        .order_by(SessionMessage.message_index.desc())
        .limit(30)
    )
    candidates = (await db.execute(stmt)).scalars().all()
    normalized_hint = text_hint.strip()
    if not normalized_hint:
        return None

    for candidate in candidates:
        payload = candidate.message if isinstance(candidate.message, dict) else {}
        if not payload or not _wappi_message_is_manager(payload):
            continue
        if _wappi_message_has_failed_status(payload):
            continue
        payload_channel_type = _wappi_outbound_channel_type_from_payload(payload)
        if payload_channel_type and payload_channel_type != channel_type:
            continue
        if _wappi_extract_manager_text(payload) != normalized_hint:
            continue
        created_at = candidate.created_at
        created_at_naive = created_at.replace(tzinfo=None) if created_at and created_at.tzinfo else created_at
        if created_at_naive and (datetime.utcnow() - created_at_naive).total_seconds() > 3600:
            continue
        return candidate
    return None


async def _wappi_update_outgoing_message(
    db: AsyncSession,
    *,
    agent_id: UUID,
    session_id: str,
    session_message: SessionMessage,
    status_value: str,
    provider_message_id: str | None = None,
    provider_task_id: str | None = None,
    provider_uuid: str | None = None,
    wh_type: str | None = None,
) -> bool:
    message_payload = session_message.message if isinstance(session_message.message, dict) else {}
    message_payload = {**message_payload}
    current_status = _wappi_normalize_delivery_status(message_payload.get("status")) or "sent"
    if _wappi_delivery_status_rank(status_value) < _wappi_delivery_status_rank(current_status):
        return False

    message_payload["status"] = status_value
    if wh_type:
        message_payload["wappi_wh_type"] = wh_type
    if provider_message_id:
        message_payload["provider_message_id"] = provider_message_id
    if provider_task_id:
        message_payload["provider_task_id"] = provider_task_id
    if provider_uuid:
        message_payload["provider_uuid"] = provider_uuid
    message_payload["delivery_status_updated_at"] = datetime.utcnow().isoformat()
    session_message.message = message_payload
    await db.commit()

    await broadcaster.publish(
        agent_id,
        {
            "type": "message_updated",
            "data": {
                "id": str(session_message.id),
                "session_id": session_id,
                "agent_id": str(agent_id),
                "status": status_value,
                "provider_message_id": provider_message_id,
            },
        },
    )
    return True


async def _update_wappi_phone_outgoing_status(
    db: AsyncSession,
    *,
    agent_id: UUID,
    agent: Agent,
    session_id: str,
    channel_type: str,
    provider_message_id: str | None,
    provider_task_id: str | None,
    provider_uuid: str | None,
    new_status: str,
) -> bool:
    session_message = await _wappi_find_outgoing_message_candidate(
        db,
        agent_id=agent_id,
        agent=agent,
        session_id=session_id,
        channel_type=channel_type,
        provider_message_id=provider_message_id,
        provider_task_id=provider_task_id,
        provider_uuid=provider_uuid,
    )
    if session_message is None:
        return False
    return await _wappi_update_outgoing_message(
        db,
        agent_id=agent_id,
        session_id=session_id,
        session_message=session_message,
        status_value=new_status,
        provider_message_id=provider_message_id,
        provider_task_id=provider_task_id,
        provider_uuid=provider_uuid,
    )


async def _link_or_append_wappi_operator_message(
    db: AsyncSession,
    *,
    agent_id: UUID,
    agent: Agent,
    session_id: str,
    input_text: str,
    base_user_info: dict[str, Any],
    log_source: str,
    wh_type: str,
    channel_type: str,
    initial_status: str,
    provider_message_id: str | None,
    provider_task_id: str | None,
    provider_uuid: str | None,
) -> None:
    candidate = await _wappi_find_outgoing_message_candidate(
        db,
        agent_id=agent_id,
        agent=agent,
        session_id=session_id,
        channel_type=channel_type,
        provider_message_id=provider_message_id,
        provider_task_id=provider_task_id,
        provider_uuid=provider_uuid,
        text_hint=input_text,
    )
    if candidate is not None:
        await _wappi_update_outgoing_message(
            db,
            agent_id=agent_id,
            session_id=session_id,
            session_message=candidate,
            status_value=initial_status,
            provider_message_id=provider_message_id,
            provider_task_id=provider_task_id,
            provider_uuid=provider_uuid,
            wh_type=wh_type,
        )
        return

    message_metadata: dict[str, Any] = {
        "status": initial_status,
        "wappi_wh_type": wh_type,
        "outbound_channel_type": channel_type,
    }
    if provider_message_id:
        message_metadata["provider_message_id"] = provider_message_id
    if provider_task_id:
        message_metadata["provider_task_id"] = provider_task_id
    if provider_uuid:
        message_metadata["provider_uuid"] = provider_uuid
    await append_wappi_linked_account_message(
        db,
        agent,
        session_id=session_id,
        text=input_text,
        base_user_info=base_user_info,
        log_source=log_source,
        message_metadata=message_metadata,
    )


async def _handle_wappi_telegram_phone_messages(
    db: AsyncSession,
    *,
    channel: Channel,
    agent_id: UUID,
    agent: Agent,
    parsed_json: dict[str, Any],
) -> None:
    profile_id = (channel.wappi_profile_id or "").strip()
    if not profile_id:
        return

    for raw_msg in _wappi_coerce_message_dicts(parsed_json):
        wh_type = str(raw_msg.get("wh_type") or "").strip().lower()
        provider_message_id = _wappi_extract_provider_message_id(raw_msg)
        provider_task_id = _wappi_extract_provider_task_id(raw_msg)
        provider_uuid = _wappi_extract_provider_uuid(raw_msg)
        chat_key = _wappi_telegram_reply_recipient(raw_msg)

        if wh_type in _WAPPI_DELIVERY_EVENT_TYPES:
            delivery_status = _wappi_normalize_delivery_status(raw_msg.get("status"))
            if not delivery_status or not chat_key:
                continue
            session_id = f"telegram_phone:{chat_key}"
            try:
                updated = await _update_wappi_phone_outgoing_status(
                    db,
                    agent_id=agent_id,
                    agent=agent,
                    session_id=session_id,
                    channel_type="telegram_phone",
                    provider_message_id=provider_message_id,
                    provider_task_id=provider_task_id,
                    provider_uuid=provider_uuid,
                    new_status=delivery_status,
                )
                if not updated:
                    logger.info(
                        "wappi_telegram_phone_delivery_status_message_not_found",
                        channel_id=str(channel.id),
                        agent_id=str(agent_id),
                        session_id=session_id,
                        provider_message_id=provider_message_id,
                        status=delivery_status,
                    )
            except Exception as exc:
                logger.exception(
                    "wappi_telegram_phone_delivery_status_update_failed",
                    channel_id=str(channel.id),
                    agent_id=str(agent_id),
                    provider_message_id=provider_message_id,
                    status=delivery_status,
                    error=str(exc),
                )
            continue

        if wh_type not in _WAPPI_TELEGRAM_TEXT_EVENT_TYPES:
            continue

        platform_raw = str(raw_msg.get("platform") or "").strip().lower()
        if platform_raw != "telegram":
            continue
        if _coerce_bool(raw_msg.get("is_bot")) is True:
            continue
        if not _wappi_is_private_chat(raw_msg, channel_type="telegram_phone"):
            continue
        if not _wappi_is_text_message(raw_msg):
            continue
        input_text = _wappi_extract_text_body(raw_msg)
        if not input_text:
            continue

        if not chat_key:
            continue

        session_id = f"telegram_phone:{chat_key}"
        user_info = _wappi_telegram_phone_user_info(raw_msg, chat_id_str=chat_key, channel=channel)
        linked_account_message = wh_type == "outgoing_message_phone" or _wappi_is_from_linked_account(raw_msg)

        if linked_account_message:
            if _wappi_likely_api_automated_send(raw_msg):
                continue
            operator_user_info = _wappi_phone_operator_user_info(user_info, channel_type=channel.type)
            initial_status = _wappi_normalize_delivery_status(raw_msg.get("status")) or "sent"
            try:
                await _link_or_append_wappi_operator_message(
                    db,
                    agent_id=agent_id,
                    agent=agent,
                    session_id=session_id,
                    input_text=input_text,
                    base_user_info=operator_user_info,
                    log_source="wappi_telegram_phone_operator",
                    wh_type=wh_type,
                    channel_type="telegram_phone",
                    initial_status=initial_status,
                    provider_message_id=provider_message_id,
                    provider_task_id=provider_task_id,
                    provider_uuid=provider_uuid,
                )
            except Exception as exc:
                logger.exception(
                    "wappi_telegram_phone_operator_message_failed",
                    channel_id=str(channel.id),
                    agent_id=str(agent_id),
                    session_id=session_id,
                    error=str(exc),
                )
            continue

        dialog_active = await is_dialog_active(db, agent_id, session_id)
        manager_paused = False
        if dialog_active:
            manager_paused = await is_manager_paused(db, agent_id, session_id)

        from_id = str(raw_msg.get("from") or "").strip()
        platform_user_id = from_id or chat_key

        user_disabled = await is_agent_user_disabled(
            db,
            tenant_id=agent.tenant_id,
            agent_id=agent_id,
            platform="telegram_phone",
            platform_user_id=platform_user_id,
        )

        should_run_agent = (
            dialog_active
            and not manager_paused
            and not agent.is_disabled
            and not user_disabled
        )

        if should_run_agent:
            reply = await process_webhook_inbound_agent_message(
                db,
                agent,
                session_id=session_id,
                input_text=input_text,
                user_info=user_info,
                run_agent=True,
                log_source="wappi_telegram_phone",
            )
            if reply:
                reply_text = sanitize_agent_reply_text(reply)
                if reply_text:
                    try:
                        client = build_wappi_client()
                        timeout_from, timeout_to = resolve_wappi_async_timeout_range()
                        await client.send_telegram_async_message(
                            profile_id=profile_id,
                            body=reply_text,
                            recipient=chat_key,
                            timeout_from=timeout_from,
                            timeout_to=timeout_to,
                        )
                    except (WappiClientError, ChannelProfileConfigError) as exc:
                        logger.warning(
                            "wappi_telegram_send_reply_failed",
                            channel_id=str(channel.id),
                            agent_id=str(agent_id),
                            error=str(exc),
                        )
        else:
            if agent.is_disabled:
                skip_reason = "agent_disabled"
            elif user_disabled:
                skip_reason = "agent_user_disabled"
            elif manager_paused:
                skip_reason = "manager_paused"
            else:
                skip_reason = "dialog_inactive"
            logger.info(
                "wappi_telegram_phone_message_skipped",
                reason=skip_reason,
                channel_id=str(channel.id),
                agent_id=str(agent_id),
                session_id=session_id,
            )
            try:
                await process_webhook_inbound_agent_message(
                    db,
                    agent,
                    session_id=session_id,
                    input_text=input_text,
                    user_info=user_info,
                    run_agent=False,
                    log_source="wappi_telegram_phone",
                )
            except Exception as exc:
                logger.exception(
                    "wappi_telegram_phone_save_without_agent_failed",
                    reason=skip_reason,
                    channel_id=str(channel.id),
                    agent_id=str(agent_id),
                    error=str(exc),
                )


async def _handle_wappi_whatsapp_messages(
    db: AsyncSession,
    *,
    channel: Channel,
    agent_id: UUID,
    agent: Agent,
    parsed_json: dict[str, Any],
) -> None:
    profile_id = (channel.wappi_profile_id or "").strip()
    if not profile_id:
        return

    for raw_msg in _wappi_coerce_message_dicts(parsed_json):
        wh_type = str(raw_msg.get("wh_type") or "").strip().lower()
        provider_message_id = _wappi_extract_provider_message_id(raw_msg)
        provider_task_id = _wappi_extract_provider_task_id(raw_msg)
        provider_uuid = _wappi_extract_provider_uuid(raw_msg)
        chat_key = _wappi_whatsapp_reply_recipient(raw_msg)

        if wh_type in _WAPPI_DELIVERY_EVENT_TYPES:
            delivery_status = _wappi_normalize_delivery_status(raw_msg.get("status"))
            if not delivery_status or not chat_key:
                continue
            session_id = f"whatsapp:{chat_key}"
            try:
                updated = await _update_wappi_phone_outgoing_status(
                    db,
                    agent_id=agent_id,
                    agent=agent,
                    session_id=session_id,
                    channel_type="whatsapp",
                    provider_message_id=provider_message_id,
                    provider_task_id=provider_task_id,
                    provider_uuid=provider_uuid,
                    new_status=delivery_status,
                )
                if not updated:
                    logger.info(
                        "wappi_whatsapp_delivery_status_message_not_found",
                        channel_id=str(channel.id),
                        agent_id=str(agent_id),
                        session_id=session_id,
                        provider_message_id=provider_message_id,
                        status=delivery_status,
                    )
            except Exception as exc:
                logger.exception(
                    "wappi_whatsapp_delivery_status_update_failed",
                    channel_id=str(channel.id),
                    agent_id=str(agent_id),
                    provider_message_id=provider_message_id,
                    status=delivery_status,
                    error=str(exc),
                )
            continue

        if wh_type not in _WAPPI_WHATSAPP_TEXT_EVENT_TYPES:
            continue
        platform_raw = str(raw_msg.get("platform") or "").strip().lower()
        if platform_raw and platform_raw not in {"whatsapp", "wa"}:
            continue
        if _coerce_bool(raw_msg.get("is_bot")) is True:
            continue
        if not _wappi_is_private_chat(raw_msg, channel_type="whatsapp"):
            continue
        if not _wappi_is_text_message(raw_msg):
            continue
        input_text = _wappi_extract_text_body(raw_msg)
        if not input_text or not chat_key:
            continue

        session_id = f"whatsapp:{chat_key}"
        user_info = _wappi_whatsapp_user_info(raw_msg, session_peer=chat_key, channel=channel)
        linked_account_message = wh_type == "outgoing_message_phone" or _wappi_is_from_linked_account(raw_msg)

        if linked_account_message:
            if _wappi_likely_api_automated_send(raw_msg):
                continue
            try:
                operator_user_info = _wappi_phone_operator_user_info(user_info, channel_type=channel.type)
                initial_status = _wappi_normalize_delivery_status(raw_msg.get("status")) or "sent"
                await _link_or_append_wappi_operator_message(
                    db,
                    agent_id=agent_id,
                    agent=agent,
                    session_id=session_id,
                    input_text=input_text,
                    base_user_info=operator_user_info,
                    log_source="wappi_whatsapp_operator",
                    wh_type=wh_type,
                    channel_type="whatsapp",
                    initial_status=initial_status,
                    provider_message_id=provider_message_id,
                    provider_task_id=provider_task_id,
                    provider_uuid=provider_uuid,
                )
            except Exception as exc:
                logger.exception(
                    "wappi_whatsapp_operator_message_failed",
                    channel_id=str(channel.id),
                    agent_id=str(agent_id),
                    session_id=session_id,
                    error=str(exc),
                )
            continue

        dialog_active = await is_dialog_active(db, agent_id, session_id)
        manager_paused = False
        if dialog_active:
            manager_paused = await is_manager_paused(db, agent_id, session_id)

        from_id = str(raw_msg.get("from") or "").strip()
        platform_user_id = from_id or chat_key
        user_disabled = await is_agent_user_disabled(
            db,
            tenant_id=agent.tenant_id,
            agent_id=agent_id,
            platform="whatsapp",
            platform_user_id=platform_user_id,
        )

        should_run_agent = (
            dialog_active
            and not manager_paused
            and not agent.is_disabled
            and not user_disabled
        )

        if should_run_agent:
            reply = await process_webhook_inbound_agent_message(
                db,
                agent,
                session_id=session_id,
                input_text=input_text,
                user_info=user_info,
                run_agent=True,
                log_source="wappi_whatsapp",
            )
            if reply:
                reply_text = sanitize_agent_reply_text(reply)
                recipient_for_send = _wappi_whatsapp_send_recipient(chat_key)
                if reply_text and recipient_for_send:
                    try:
                        client = build_wappi_client()
                        timeout_from, timeout_to = resolve_wappi_async_timeout_range()
                        await client.send_whatsapp_async_message(
                            profile_id=profile_id,
                            body=reply_text,
                            recipient=recipient_for_send,
                            timeout_from=timeout_from,
                            timeout_to=timeout_to,
                        )
                    except (WappiClientError, ChannelProfileConfigError) as exc:
                        logger.warning(
                            "wappi_whatsapp_send_reply_failed",
                            channel_id=str(channel.id),
                            agent_id=str(agent_id),
                            error=str(exc),
                        )
                elif reply_text and not recipient_for_send:
                    logger.warning(
                        "wappi_whatsapp_send_reply_skipped_missing_recipient",
                        channel_id=str(channel.id),
                        agent_id=str(agent_id),
                        session_id=session_id,
                        chat_key=chat_key,
                    )
        else:
            if agent.is_disabled:
                skip_reason = "agent_disabled"
            elif user_disabled:
                skip_reason = "agent_user_disabled"
            elif manager_paused:
                skip_reason = "manager_paused"
            else:
                skip_reason = "dialog_inactive"
            logger.info(
                "wappi_whatsapp_message_skipped",
                reason=skip_reason,
                channel_id=str(channel.id),
                agent_id=str(agent_id),
                session_id=session_id,
            )
            try:
                await process_webhook_inbound_agent_message(
                    db,
                    agent,
                    session_id=session_id,
                    input_text=input_text,
                    user_info=user_info,
                    run_agent=False,
                    log_source="wappi_whatsapp",
                )
            except Exception as exc:
                logger.exception(
                    "wappi_whatsapp_save_without_agent_failed",
                    reason=skip_reason,
                    channel_id=str(channel.id),
                    agent_id=str(agent_id),
                    error=str(exc),
                )


def _wappi_max_send_ids(msg: dict[str, Any]) -> tuple[str | None, str | None]:
    """(recipient, chat_id) для maxapi/sync/message/send и session_id."""
    chat_peer: str | None = None
    for key in ("chatId", "chat_id", "to", "dialog_id", "dialogId", "peer_id", "peerId"):
        raw = msg.get(key)
        if raw is None:
            continue
        s = str(raw).strip()
        if s:
            chat_peer = s
            break
    recipient = str(
        msg.get("recipient")
        or msg.get("phone")
        or msg.get("contact_phone")
        or msg.get("contactPhone")
        or msg.get("contact_id")
        or msg.get("contactId")
        or ""
    ).strip()
    if not recipient:
        from_id = str(msg.get("from") or "").strip()
        if from_id.isdigit():
            recipient = from_id
    return (recipient or None), chat_peer


def _wappi_max_user_info(
    msg: dict[str, Any],
    *,
    session_peer: str,
    channel: Channel,
) -> dict[str, Any]:
    return _wappi_base_phone_user_info(
        msg,
        session_peer=session_peer,
        channel=channel,
        platform_name="max",
    )


def _wappi_whatsapp_user_info(
    msg: dict[str, Any],
    *,
    session_peer: str,
    channel: Channel,
) -> dict[str, Any]:
    return _wappi_base_phone_user_info(
        msg,
        session_peer=session_peer,
        channel=channel,
        platform_name="whatsapp",
    )


async def _handle_wappi_max_incoming_messages(
    db: AsyncSession,
    *,
    channel: Channel,
    agent_id: UUID,
    agent: Agent,
    parsed_json: dict[str, Any],
) -> None:
    profile_id = (channel.wappi_profile_id or "").strip()
    if not profile_id:
        return

    bot_id = (resolve_wappi_max_bot_id(channel) or "").strip()

    message_dicts = _wappi_coerce_message_dicts(parsed_json)
    if not message_dicts:
        return

    for raw_msg in message_dicts:
        wh_type = str(raw_msg.get("wh_type") or "").strip().lower()
        provider_message_id = _wappi_extract_provider_message_id(raw_msg)
        provider_task_id = _wappi_extract_provider_task_id(raw_msg)
        provider_uuid = _wappi_extract_provider_uuid(raw_msg)
        recipient, chat_peer = _wappi_max_send_ids(raw_msg)
        from_raw = str(raw_msg.get("from") or "").strip()
        session_peer = chat_peer or recipient or from_raw

        if wh_type in _WAPPI_DELIVERY_EVENT_TYPES:
            delivery_status = _wappi_normalize_delivery_status(raw_msg.get("status"))
            if not delivery_status or not session_peer:
                continue
            session_id = f"max:{session_peer}"
            try:
                updated = await _update_wappi_phone_outgoing_status(
                    db,
                    agent_id=agent_id,
                    agent=agent,
                    session_id=session_id,
                    channel_type="max",
                    provider_message_id=provider_message_id,
                    provider_task_id=provider_task_id,
                    provider_uuid=provider_uuid,
                    new_status=delivery_status,
                )
                if not updated:
                    logger.info(
                        "wappi_max_delivery_status_message_not_found",
                        channel_id=str(channel.id),
                        agent_id=str(agent_id),
                        session_id=session_id,
                        provider_message_id=provider_message_id,
                        status=delivery_status,
                    )
            except Exception as exc:
                logger.exception(
                    "wappi_max_delivery_status_update_failed",
                    channel_id=str(channel.id),
                    agent_id=str(agent_id),
                    provider_message_id=provider_message_id,
                    status=delivery_status,
                    error=str(exc),
                )
            continue

        if not _wappi_max_wh_type_is_chat_message(wh_type):
            continue
        plat_raw = raw_msg.get("platform")
        if plat_raw is not None and str(plat_raw).strip():
            if not _wappi_platform_is_max(plat_raw):
                continue
        if _coerce_bool(raw_msg.get("is_bot")) is True:
            continue
        if not _wappi_is_private_chat(raw_msg, channel_type="max"):
            continue
        if not _wappi_is_text_message(raw_msg):
            continue
        input_text = _wappi_extract_text_body(raw_msg)
        if not input_text:
            continue

        if not session_peer:
            logger.info(
                "wappi_max_message_skipped_no_peer",
                channel_id=str(channel.id),
                agent_id=str(agent_id),
            )
            continue

        session_id = f"max:{session_peer}"
        user_info = _wappi_max_user_info(raw_msg, session_peer=session_peer, channel=channel)
        linked_account_message = wh_type == "outgoing_message_phone" or _wappi_is_from_linked_account(raw_msg)

        if linked_account_message:
            if _wappi_likely_api_automated_send(raw_msg):
                continue
            try:
                operator_user_info = _wappi_phone_operator_user_info(user_info, channel_type=channel.type)
                initial_status = _wappi_normalize_delivery_status(raw_msg.get("status")) or "sent"
                await _link_or_append_wappi_operator_message(
                    db,
                    agent_id=agent_id,
                    agent=agent,
                    session_id=session_id,
                    input_text=input_text,
                    base_user_info=operator_user_info,
                    log_source="wappi_max_operator",
                    wh_type=wh_type,
                    channel_type="max",
                    initial_status=initial_status,
                    provider_message_id=provider_message_id,
                    provider_task_id=provider_task_id,
                    provider_uuid=provider_uuid,
                )
            except Exception as exc:
                logger.exception(
                    "wappi_max_operator_message_failed",
                    channel_id=str(channel.id),
                    agent_id=str(agent_id),
                    session_id=session_id,
                    error=str(exc),
                )
            continue

        dialog_active = await is_dialog_active(db, agent_id, session_id)
        manager_paused = False
        if dialog_active:
            manager_paused = await is_manager_paused(db, agent_id, session_id)

        from_id = str(raw_msg.get("from") or "").strip()
        platform_user_id = from_id or recipient or session_peer

        user_disabled = await is_agent_user_disabled(
            db,
            tenant_id=agent.tenant_id,
            agent_id=agent_id,
            platform="max",
            platform_user_id=platform_user_id,
        )

        should_run_agent = (
            dialog_active
            and not manager_paused
            and not agent.is_disabled
            and not user_disabled
        )

        if should_run_agent:
            reply = await process_webhook_inbound_agent_message(
                db,
                agent,
                session_id=session_id,
                input_text=input_text,
                user_info=user_info,
                run_agent=True,
                log_source="wappi_max",
            )
            if reply:
                reply_text = sanitize_agent_reply_text(reply)
                if reply_text and bot_id and (recipient or chat_peer):
                    try:
                        client = build_wappi_client()
                        timeout_from, timeout_to = resolve_wappi_async_timeout_range()
                        await client.send_max_async_message(
                            profile_id=profile_id,
                            body=reply_text,
                            recipient=recipient,
                            chat_id=chat_peer,
                            bot_id=bot_id,
                            timeout_from=timeout_from,
                            timeout_to=timeout_to,
                        )
                    except (WappiClientError, ChannelProfileConfigError) as exc:
                        logger.warning(
                            "wappi_max_send_reply_failed",
                            channel_id=str(channel.id),
                            agent_id=str(agent_id),
                            error=str(exc),
                        )
                elif reply_text and (not bot_id or (not recipient and not chat_peer)):
                    logger.warning(
                        "wappi_max_send_reply_skipped_missing_params",
                        channel_id=str(channel.id),
                        agent_id=str(agent_id),
                        has_bot_id=bool(bot_id),
                        has_recipient=bool(recipient),
                        has_chat_id=bool(chat_peer),
                    )
        else:
            if agent.is_disabled:
                skip_reason = "agent_disabled"
            elif user_disabled:
                skip_reason = "agent_user_disabled"
            elif manager_paused:
                skip_reason = "manager_paused"
            else:
                skip_reason = "dialog_inactive"
            logger.info(
                "wappi_max_message_skipped",
                reason=skip_reason,
                channel_id=str(channel.id),
                agent_id=str(agent_id),
                session_id=session_id,
            )
            try:
                await process_webhook_inbound_agent_message(
                    db,
                    agent,
                    session_id=session_id,
                    input_text=input_text,
                    user_info=user_info,
                    run_agent=False,
                    log_source="wappi_max",
                )
            except Exception as exc:
                logger.exception(
                    "wappi_max_save_without_agent_failed",
                    reason=skip_reason,
                    channel_id=str(channel.id),
                    agent_id=str(agent_id),
                    error=str(exc),
                )


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
    expected_secret = str(channel.wappi_webhook_secret or "").strip()
    if expected_secret:
        provided_secret = _extract_phone_webhook_auth_secret(request)
        if not provided_secret or not secrets.compare_digest(provided_secret, expected_secret):
            wappi_webhook_logger.warning(
                "phone_channel_webhook_secret_invalid",
                channel_id=str(channel.id),
                channel_type=channel.type,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook secret",
            )

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
    platform_wappi_logger = _WAPPI_PLATFORM_WEBHOOK_LOGGERS.get(channel.type)
    if platform_wappi_logger is not None:
        platform_wappi_logger.info("phone_channel_webhook_incoming", **log_payload)
    logger.info("phone_channel_webhook_received", **log_payload)

    if channel.type in ("telegram_phone", "whatsapp", "max") and isinstance(parsed_json, dict):
        stmt_agent = (
            select(AgentChannel.agent_id, Agent)
            .join(Agent, Agent.id == AgentChannel.agent_id)
            .where(
                AgentChannel.channel_id == channel_id,
                Agent.is_deleted.is_(False),
            )
        )
        agent_row = (await db.execute(stmt_agent)).first()
        if agent_row is not None:
            bound_agent_id, bound_agent = agent_row
            if channel.type == "telegram_phone":
                await _handle_wappi_telegram_phone_messages(
                    db,
                    channel=channel,
                    agent_id=bound_agent_id,
                    agent=bound_agent,
                    parsed_json=parsed_json,
                )
            elif channel.type == "whatsapp":
                await _handle_wappi_whatsapp_messages(
                    db,
                    channel=channel,
                    agent_id=bound_agent_id,
                    agent=bound_agent,
                    parsed_json=parsed_json,
                )
            elif channel.type == "max":
                await _handle_wappi_max_incoming_messages(
                    db,
                    channel=channel,
                    agent_id=bound_agent_id,
                    agent=bound_agent,
                    parsed_json=parsed_json,
                )

    return {"ok": True}
