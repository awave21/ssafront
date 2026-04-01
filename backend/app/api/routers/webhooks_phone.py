from __future__ import annotations

import json
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
from app.core.config import get_settings
from app.db.models.agent import Agent
from app.db.models.channel import AgentChannel, Channel
from app.db.session import get_db
from app.services.agent_user_state import is_agent_user_disabled
from app.services.dialog_state import is_dialog_active, is_manager_paused
from app.services.wappi import WappiClientError, build_wappi_client
from app.services.wappi.binding import ChannelProfileConfigError

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


_PHONE_CHANNEL_LABELS: dict[str, str] = {
    "telegram_phone": "Telegram (личный номер)",
    "whatsapp": "WhatsApp",
    "max": "MAX",
}


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


def _wappi_incoming_is_private_chat(msg: dict[str, Any]) -> bool:
    """
    Только личные переписки: не группы/каналы (Telegram phone / tapi).
    Wappi для групп часто шлёт chat_type \"chat\"; для лички — \"private\" или совпадение from с peer id.
    Отрицательный peer id (chatId/chat_id) — как правило супергруппа/чат в Telegram.
    """
    ct = str(msg.get("chat_type") or "").strip().lower()
    if ct in ("group", "supergroup", "channel", "chat", "megagroup"):
        return False
    if ct in ("private", "user", "dialog", "direct", "dm", "personal"):
        return True
    peer = str(msg.get("chatId") or msg.get("chat_id") or msg.get("to") or "").strip()
    if peer.startswith("-"):
        return False
    from_id = str(msg.get("from") or "").strip()
    if from_id and peer and from_id == peer:
        return True
    return False


def _wappi_max_accepts_dialog(msg: dict[str, Any]) -> bool:
    """
    MAX (maxapi): peer id часто отрицательный и у лички, from может быть телефоном, а chatId — другим id.
    Отсекаем только явные группы/каналы по chat_type.
    """
    ct = str(msg.get("chat_type") or "").strip().lower()
    return ct not in ("group", "supergroup", "channel", "chat", "megagroup")


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
    return w in {
        "incoming_message",
        "outgoing_message",
        "out_message",
        "message",
        "new_message",
        "dialog_message",
    }


def _wappi_telegram_reply_recipient(msg: dict[str, Any]) -> str | None:
    """Идентификатор чата для ответа (tapi sync message send)."""
    for key in ("chatId", "to"):
        raw = msg.get(key)
        if raw is None:
            continue
        s = str(raw).strip()
        if s:
            return s
    return None


def _wappi_telegram_phone_user_info(
    msg: dict[str, Any],
    *,
    chat_id_str: str,
    channel: Channel,
) -> dict[str, Any]:
    from_id = str(msg.get("from") or "").strip() or chat_id_str
    info: dict[str, Any] = {
        "platform": "telegram_phone",
        "platform_id": from_id,
        "integration_channel_type": channel.type,
        "integration_channel_label": _PHONE_CHANNEL_LABELS.get(
            channel.type,
            channel.type.replace("_", " ").title(),
        ),
    }
    if isinstance(msg.get("username"), str) and msg["username"].strip():
        info["username"] = msg["username"].strip()
    if isinstance(msg.get("senderName"), str) and msg["senderName"].strip():
        info["first_name"] = msg["senderName"].strip()
    if isinstance(msg.get("senderLastName"), str) and msg["senderLastName"].strip():
        info["last_name"] = msg["senderLastName"].strip()
    info["wappi_direction"] = "in"
    info["message_sender_kind"] = "contact"
    return info


async def _handle_wappi_telegram_phone_incoming_messages(
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
        if wh_type != "incoming_message":
            continue
        platform_raw = str(raw_msg.get("platform") or "").strip().lower()
        if platform_raw != "telegram":
            continue
        if _coerce_bool(raw_msg.get("is_bot")) is True:
            continue
        if not _wappi_incoming_is_private_chat(raw_msg):
            continue
        msg_type = str(raw_msg.get("type") or "").strip().lower()
        if msg_type and msg_type not in ("text", "chat", "message", "plain"):
            continue
        input_text = _wappi_extract_text_body(raw_msg)
        if not input_text:
            continue

        chat_key = _wappi_telegram_reply_recipient(raw_msg)
        if not chat_key:
            continue

        session_id = f"telegram_phone:{chat_key}"
        user_info = _wappi_telegram_phone_user_info(raw_msg, chat_id_str=chat_key, channel=channel)

        if _wappi_is_from_linked_account(raw_msg):
            if _wappi_likely_api_automated_send(raw_msg):
                continue
            try:
                await append_wappi_linked_account_message(
                    db,
                    agent,
                    session_id=session_id,
                    text=input_text,
                    base_user_info=user_info,
                    log_source="wappi_telegram_phone_operator",
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
                        await client.send_telegram_sync_message(
                            profile_id=profile_id,
                            body=reply_text,
                            recipient=chat_key,
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
    from_id = str(msg.get("from") or "").strip() or session_peer
    info: dict[str, Any] = {
        "platform": "max",
        "platform_id": from_id,
        "integration_channel_type": channel.type,
        "integration_channel_label": _PHONE_CHANNEL_LABELS.get(
            channel.type,
            channel.type.replace("_", " ").title(),
        ),
    }
    if isinstance(msg.get("username"), str) and msg["username"].strip():
        info["username"] = msg["username"].strip()
    if isinstance(msg.get("senderName"), str) and msg["senderName"].strip():
        info["first_name"] = msg["senderName"].strip()
    if isinstance(msg.get("senderLastName"), str) and msg["senderLastName"].strip():
        info["last_name"] = msg["senderLastName"].strip()
    info["wappi_direction"] = "in"
    info["message_sender_kind"] = "contact"
    return info


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

    bot_id = (channel.wappi_max_bot_id or "").strip()
    if not bot_id:
        bot_id = (get_settings().wappi_max_default_bot_id or "").strip()

    message_dicts = _wappi_coerce_message_dicts(parsed_json)
    if not message_dicts:
        return

    for raw_msg in message_dicts:
        wh_type = str(raw_msg.get("wh_type") or "").strip().lower()
        if not _wappi_max_wh_type_is_chat_message(wh_type):
            continue
        plat_raw = raw_msg.get("platform")
        if plat_raw is not None and str(plat_raw).strip():
            if not _wappi_platform_is_max(plat_raw):
                continue
        if _coerce_bool(raw_msg.get("is_bot")) is True:
            continue
        if not _wappi_max_accepts_dialog(raw_msg):
            continue
        msg_type = str(raw_msg.get("type") or "").strip().lower()
        if msg_type and msg_type not in ("text", "chat", "message", "plain"):
            continue
        input_text = _wappi_extract_text_body(raw_msg)
        if not input_text:
            continue

        recipient, chat_peer = _wappi_max_send_ids(raw_msg)
        from_raw = str(raw_msg.get("from") or "").strip()
        session_peer = chat_peer or recipient or from_raw
        if not session_peer:
            logger.info(
                "wappi_max_message_skipped_no_peer",
                channel_id=str(channel.id),
                agent_id=str(agent_id),
            )
            continue

        session_id = f"max:{session_peer}"
        user_info = _wappi_max_user_info(raw_msg, session_peer=session_peer, channel=channel)

        if _wappi_is_from_linked_account(raw_msg):
            if _wappi_likely_api_automated_send(raw_msg):
                continue
            try:
                await append_wappi_linked_account_message(
                    db,
                    agent,
                    session_id=session_id,
                    text=input_text,
                    base_user_info=user_info,
                    log_source="wappi_max_operator",
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
                if reply_text and bot_id and recipient and chat_peer:
                    try:
                        client = build_wappi_client()
                        await client.send_max_sync_message(
                            profile_id=profile_id,
                            bot_id=bot_id,
                            body=reply_text,
                            recipient=recipient,
                            chat_id=chat_peer,
                        )
                    except (WappiClientError, ChannelProfileConfigError) as exc:
                        logger.warning(
                            "wappi_max_send_reply_failed",
                            channel_id=str(channel.id),
                            agent_id=str(agent_id),
                            error=str(exc),
                        )
                elif reply_text and (not bot_id or not recipient or not chat_peer):
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

    if channel.type in ("telegram_phone", "max") and isinstance(parsed_json, dict):
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
                await _handle_wappi_telegram_phone_incoming_messages(
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
