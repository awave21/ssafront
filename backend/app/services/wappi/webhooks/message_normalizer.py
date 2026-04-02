from __future__ import annotations

from typing import Any

from app.db.models.channel import Channel
from app.services.wappi.webhooks.auth_state import coerce_bool

PHONE_CHANNEL_LABELS: dict[str, str] = {
    "telegram_phone": "Telegram номер",
    "whatsapp": "WhatsApp",
    "max": "MAX",
}

WAPPI_TELEGRAM_TEXT_EVENT_TYPES = {"incoming_message", "outgoing_message_phone"}
WAPPI_WHATSAPP_TEXT_EVENT_TYPES = {"incoming_message", "outgoing_message_phone"}
WAPPI_MAX_TEXT_EVENT_TYPES = {
    "incoming_message",
    "outgoing_message_phone",
    "outgoing_message",
    "out_message",
    "message",
    "new_message",
    "dialog_message",
}
WAPPI_DELIVERY_EVENT_TYPES = {"delivery_status"}
WAPPI_TEXT_MESSAGE_TYPES = {"text", "chat", "message", "plain"}
WAPPI_IGNORED_NON_TEXT_TYPES = {"image", "document", "video", "ptt", "audio"}
WAPPI_DELIVERY_STATUS_RANK: dict[str, int] = {
    "sent": 1,
    "delivered": 2,
    "read": 3,
}
WAPPI_DELIVERY_STATUS_ALIAS: dict[str, str] = {
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


def contact_sender_display_label(channel_type: str) -> str:
    channel_label = PHONE_CHANNEL_LABELS.get(channel_type, channel_type.replace("_", " ").title())
    return f"Клиент ({channel_label})"


def operator_sender_display_label(channel_type: str) -> str:
    channel_label = PHONE_CHANNEL_LABELS.get(channel_type, channel_type.replace("_", " ").title())
    return f"Оператор ({channel_label})"


def is_from_linked_account(msg: dict[str, Any]) -> bool:
    for key in ("from_me", "fromMe", "outgoing", "is_me", "isMe", "fromSelf", "self"):
        if key not in msg:
            continue
        b = coerce_bool(msg.get(key))
        if b is True:
            return True
    return False


def likely_api_automated_send(msg: dict[str, Any]) -> bool:
    b = coerce_bool(msg.get("from_api") or msg.get("fromApi"))
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


def message_type(msg: dict[str, Any]) -> str:
    return str(
        msg.get("type")
        or msg.get("message_type")
        or msg.get("msg_type")
        or msg.get("media_type")
        or ""
    ).strip().lower()


def is_text_message(msg: dict[str, Any]) -> bool:
    msg_type = message_type(msg)
    if not msg_type:
        return extract_text_body(msg) is not None
    if msg_type in WAPPI_IGNORED_NON_TEXT_TYPES:
        return False
    return msg_type in WAPPI_TEXT_MESSAGE_TYPES


def is_private_chat(msg: dict[str, Any], *, channel_type: str) -> bool:
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


def platform_is_max(platform_raw: Any) -> bool:
    s = str(platform_raw or "").strip().lower()
    if not s:
        return False
    if s == "max":
        return True
    if s.startswith("max_") or s.startswith("max-"):
        return True
    return s in {"maxmessenger", "max_messenger", "maxapi", "max_api"}


def coerce_message_dicts(parsed_json: dict[str, Any]) -> list[dict[str, Any]]:
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


def extract_text_body(raw_msg: dict[str, Any]) -> str | None:
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


def max_wh_type_is_chat_message(wh_type: str) -> bool:
    w = (wh_type or "").strip().lower()
    return w in WAPPI_MAX_TEXT_EVENT_TYPES


def telegram_reply_recipient(msg: dict[str, Any]) -> str | None:
    for key in ("chatId", "chat_id", "to"):
        raw = msg.get(key)
        if raw is None:
            continue
        s = str(raw).strip()
        if s:
            return s
    return None


def whatsapp_reply_recipient(msg: dict[str, Any]) -> str | None:
    for key in ("chatId", "chat_id", "to", "recipient", "phone", "from"):
        raw = msg.get(key)
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            return value
    return None


def whatsapp_send_recipient(session_peer: str) -> str:
    normalized_peer = (session_peer or "").strip()
    if not normalized_peer:
        return ""
    lowered = normalized_peer.lower()
    if lowered.endswith("@s.whatsapp.net") or lowered.endswith("@c.us"):
        normalized_peer = normalized_peer.split("@", 1)[0]
    return "".join(ch for ch in normalized_peer if ch.isdigit()) or normalized_peer


def extract_phone_digits(value: Any) -> str | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    peer_part = raw_value.split("@", 1)[0] if "@" in raw_value else raw_value
    digits = "".join(ch for ch in peer_part if ch.isdigit())
    if len(digits) < 10 or len(digits) > 15:
        return None
    return digits


def resolve_contact_phone(msg: dict[str, Any]) -> str | None:
    explicit_contact = extract_phone_digits(msg.get("contact_phone") or msg.get("contactPhone"))
    if explicit_contact:
        return explicit_contact

    linked_account_message = is_from_linked_account(msg) or (
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
        candidate_phone = extract_phone_digits(msg.get(key))
        if candidate_phone:
            return candidate_phone
    return None


def base_phone_user_info(
    msg: dict[str, Any],
    *,
    session_peer: str,
    channel: Channel,
    platform_name: str,
) -> dict[str, Any]:
    from_id = str(msg.get("from") or "").strip() or session_peer
    channel_label = PHONE_CHANNEL_LABELS.get(channel.type, channel.type.replace("_", " ").title())
    info: dict[str, Any] = {
        "platform": platform_name,
        "platform_id": from_id,
        "integration_channel_type": channel.type,
        "integration_channel_label": channel_label,
        "wappi_direction": "in",
        "message_sender_kind": "contact",
        "sender_display_label": contact_sender_display_label(channel.type),
    }
    contact_phone = resolve_contact_phone(msg)
    if contact_phone:
        info["contact_phone"] = contact_phone
    if isinstance(msg.get("username"), str) and msg["username"].strip():
        info["username"] = msg["username"].strip()
    if isinstance(msg.get("senderName"), str) and msg["senderName"].strip():
        info["first_name"] = msg["senderName"].strip()
    if isinstance(msg.get("senderLastName"), str) and msg["senderLastName"].strip():
        info["last_name"] = msg["senderLastName"].strip()
    return info


def telegram_phone_user_info(
    msg: dict[str, Any],
    *,
    chat_id_str: str,
    channel: Channel,
) -> dict[str, Any]:
    return base_phone_user_info(
        msg,
        session_peer=chat_id_str,
        channel=channel,
        platform_name="telegram_phone",
    )


def phone_operator_user_info(base_info: dict[str, Any], *, channel_type: str) -> dict[str, Any]:
    info = {**base_info}
    info["wappi_direction"] = "out"
    info["message_sender_kind"] = "wappi_operator"
    info["sender_display_label"] = operator_sender_display_label(channel_type)
    return info


def normalize_delivery_status(raw_status: Any) -> str | None:
    value = str(raw_status or "").strip().lower()
    if not value:
        return None
    return WAPPI_DELIVERY_STATUS_ALIAS.get(value)


def extract_provider_message_id(msg: dict[str, Any]) -> str | None:
    raw = msg.get("id") or msg.get("message_id") or msg.get("messageId")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def extract_provider_task_id(msg: dict[str, Any]) -> str | None:
    raw = msg.get("task_id") or msg.get("taskId") or msg.get("queue_task_id") or msg.get("queueTaskId")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def extract_provider_uuid(msg: dict[str, Any]) -> str | None:
    raw = msg.get("uuid")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def delivery_status_rank(status_value: str | None) -> int:
    if not status_value:
        return 0
    return WAPPI_DELIVERY_STATUS_RANK.get(status_value, 0)


def extract_manager_text(message_payload: dict[str, Any]) -> str:
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


def outbound_channel_type_from_payload(message_payload: dict[str, Any]) -> str:
    direct_type = str(message_payload.get("outbound_channel_type") or "").strip().lower()
    if direct_type:
        return direct_type
    user_info = message_payload.get("user_info")
    if isinstance(user_info, dict):
        nested_type = str(user_info.get("integration_channel_type") or "").strip().lower()
        if nested_type:
            return nested_type
    return ""


def message_is_manager(message_payload: dict[str, Any]) -> bool:
    role = str(message_payload.get("role") or "").strip().lower()
    if role == "manager":
        return True
    user_info = message_payload.get("user_info")
    if isinstance(user_info, dict):
        sender_kind = str(user_info.get("message_sender_kind") or "").strip().lower()
        if sender_kind in {"manager", "wappi_operator"}:
            return True
    return False


def message_has_failed_status(message_payload: dict[str, Any]) -> bool:
    raw_status = str(message_payload.get("status") or "").strip().lower()
    return raw_status == "failed"


def max_send_ids(msg: dict[str, Any]) -> tuple[str | None, str | None]:
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


def max_user_info(
    msg: dict[str, Any],
    *,
    session_peer: str,
    channel: Channel,
) -> dict[str, Any]:
    return base_phone_user_info(
        msg,
        session_peer=session_peer,
        channel=channel,
        platform_name="max",
    )


def whatsapp_user_info(
    msg: dict[str, Any],
    *,
    session_peer: str,
    channel: Channel,
) -> dict[str, Any]:
    return base_phone_user_info(
        msg,
        session_peer=session_peer,
        channel=channel,
        platform_name="whatsapp",
    )
