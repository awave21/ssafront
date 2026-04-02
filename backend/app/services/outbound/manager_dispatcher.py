from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.channel import AgentChannel, Channel
from app.services.telegram import TelegramWebhookError, send_telegram_message
from app.services.wappi import (
    WappiAsyncMessageSendResult,
    WappiClientError,
    build_wappi_client,
    resolve_wappi_async_timeout_range,
    resolve_wappi_max_bot_id,
)
from app.services.wappi.binding import ChannelProfileConfigError

logger = structlog.get_logger(__name__)

_PHONE_CHANNEL_TYPES = {"telegram_phone", "whatsapp", "max"}


class ManagerDispatchError(Exception):
    def __init__(self, message: str, *, http_status_code: int = 400) -> None:
        super().__init__(message)
        self.http_status_code = http_status_code


@dataclass(frozen=True)
class ManagerDispatchResult:
    channel_type: str
    status: str
    provider_message_id: str | None = None
    provider_task_id: str | None = None
    provider_uuid: str | None = None
    raw: dict[str, Any] | None = None


def _split_dialog_id(dialog_id: str) -> tuple[str, str]:
    normalized = (dialog_id or "").strip()
    if ":" not in normalized:
        raise ManagerDispatchError(
            "Неподдерживаемый формат dialog_id. Ожидается <platform>:<peer>",
            http_status_code=400,
        )
    channel_type, peer = normalized.split(":", 1)
    channel_type = channel_type.strip().lower()
    peer = peer.strip()
    if not channel_type or not peer:
        raise ManagerDispatchError(
            "Неподдерживаемый формат dialog_id. Ожидается <platform>:<peer>",
            http_status_code=400,
        )
    return channel_type, peer


async def _get_agent_channel(
    db: AsyncSession,
    *,
    agent_id: UUID,
    channel_type: str,
) -> Channel | None:
    stmt = (
        select(Channel)
        .join(AgentChannel, AgentChannel.channel_id == Channel.id)
        .where(
            AgentChannel.agent_id == agent_id,
            Channel.type == channel_type,
            Channel.is_deleted.is_(False),
        )
        .order_by(Channel.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _extract_provider_message_id(raw_payload: dict[str, Any] | None) -> str | None:
    if not raw_payload:
        return None
    raw_value = (
        raw_payload.get("id")
        or raw_payload.get("message_id")
        or raw_payload.get("messageId")
        or raw_payload.get("uuid")
    )
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None


def _build_max_manager_payload(manager_user_id: UUID | None) -> dict[str, str] | None:
    if manager_user_id is None:
        return None
    return {"id": str(manager_user_id)}


def _resolve_max_recipient_and_chat_id(dialog_peer: str) -> tuple[str | None, str | None]:
    normalized_peer = (dialog_peer or "").strip()
    if not normalized_peer:
        return (None, None)

    digits_only = "".join(ch for ch in normalized_peer if ch.isdigit())
    compact_phone = normalized_peer.replace(" ", "").replace("-", "")
    looks_like_phone = (
        bool(digits_only)
        and len(digits_only) >= 10
        and compact_phone.replace("+", "").isdigit()
    )
    if looks_like_phone:
        return (digits_only, None)

    recipient = digits_only or None
    chat_id = normalized_peer
    return (recipient, chat_id)


def _normalize_whatsapp_recipient(dialog_peer: str) -> str:
    normalized_peer = (dialog_peer or "").strip()
    if not normalized_peer:
        return ""
    lowered = normalized_peer.lower()
    if lowered.endswith("@s.whatsapp.net") or lowered.endswith("@c.us"):
        normalized_peer = normalized_peer.split("@", 1)[0]
    return "".join(ch for ch in normalized_peer if ch.isdigit()) or normalized_peer


def _normalize_async_dispatch_result(
    result: WappiAsyncMessageSendResult,
    *,
    channel_type: str,
) -> ManagerDispatchResult:
    return ManagerDispatchResult(
        channel_type=channel_type,
        status="sent",
        provider_message_id=_extract_provider_message_id(result.raw),
        provider_task_id=result.task_id,
        provider_uuid=result.uuid,
        raw=result.raw,
    )


async def _dispatch_to_telegram_bot(
    db: AsyncSession,
    *,
    agent_id: UUID,
    dialog_peer: str,
    content: str,
) -> ManagerDispatchResult:
    channel = await _get_agent_channel(db, agent_id=agent_id, channel_type="telegram")
    if channel is None or not (channel.telegram_bot_token or "").strip():
        raise ManagerDispatchError(
            "Telegram channel not configured for this agent",
            http_status_code=400,
        )
    chat_id: int | str
    try:
        chat_id = int(dialog_peer)
    except ValueError:
        chat_id = dialog_peer
    try:
        response = await send_telegram_message(
            bot_token=channel.telegram_bot_token,
            chat_id=chat_id,
            text=content,
        )
    except TelegramWebhookError as exc:
        raise ManagerDispatchError(str(exc), http_status_code=502) from exc

    provider_message_id: str | None = None
    if isinstance(response, dict):
        result_obj = response.get("result")
        if isinstance(result_obj, dict) and result_obj.get("message_id") is not None:
            provider_message_id = str(result_obj.get("message_id")).strip() or None

    return ManagerDispatchResult(
        channel_type="telegram",
        status="sent",
        provider_message_id=provider_message_id,
        raw=response if isinstance(response, dict) else None,
    )


async def _dispatch_to_wappi_phone_channel(
    *,
    channel_type: str,
    channel: Channel,
    content: str,
    dialog_peer: str,
    manager_user_id: UUID | None,
) -> ManagerDispatchResult:
    profile_id = (channel.wappi_profile_id or "").strip()
    if not profile_id:
        raise ManagerDispatchError(
            f"Wappi profile is not configured for channel type '{channel_type}'",
            http_status_code=400,
        )

    timeout_from, timeout_to = resolve_wappi_async_timeout_range()
    try:
        client = build_wappi_client()
    except ChannelProfileConfigError as exc:
        raise ManagerDispatchError(str(exc), http_status_code=500) from exc

    try:
        if channel_type == "telegram_phone":
            result = await client.send_telegram_async_message(
                profile_id=profile_id,
                body=content,
                recipient=dialog_peer,
                timeout_from=timeout_from,
                timeout_to=timeout_to,
            )
            return _normalize_async_dispatch_result(result, channel_type=channel_type)

        if channel_type == "whatsapp":
            recipient = _normalize_whatsapp_recipient(dialog_peer)
            if not recipient:
                raise ManagerDispatchError(
                    "Для WhatsApp не удалось определить recipient из dialog_id",
                    http_status_code=400,
                )
            result = await client.send_whatsapp_async_message(
                profile_id=profile_id,
                body=content,
                recipient=recipient,
                timeout_from=timeout_from,
                timeout_to=timeout_to,
            )
            return _normalize_async_dispatch_result(result, channel_type=channel_type)

        if channel_type == "max":
            recipient, chat_id = _resolve_max_recipient_and_chat_id(dialog_peer)
            if not recipient and not chat_id:
                raise ManagerDispatchError(
                    "Для MAX не удалось определить recipient/chat_id из dialog_id",
                    http_status_code=400,
                )

            result = await client.send_max_async_message(
                profile_id=profile_id,
                body=content,
                recipient=recipient,
                chat_id=chat_id,
                bot_id=resolve_wappi_max_bot_id(channel),
                manager=_build_max_manager_payload(manager_user_id),
                timeout_from=timeout_from,
                timeout_to=timeout_to,
            )
            return _normalize_async_dispatch_result(result, channel_type=channel_type)
    except ManagerDispatchError:
        raise
    except (WappiClientError, ChannelProfileConfigError) as exc:
        raise ManagerDispatchError(str(exc), http_status_code=502) from exc

    raise ManagerDispatchError(
        f"Неподдерживаемый phone-канал '{channel_type}'",
        http_status_code=400,
    )


async def dispatch_manager_message(
    db: AsyncSession,
    *,
    agent_id: UUID,
    dialog_id: str,
    content: str,
    manager_user_id: UUID | None,
) -> ManagerDispatchResult:
    channel_type, dialog_peer = _split_dialog_id(dialog_id)
    if channel_type == "telegram":
        return await _dispatch_to_telegram_bot(
            db,
            agent_id=agent_id,
            dialog_peer=dialog_peer,
            content=content,
        )

    if channel_type in _PHONE_CHANNEL_TYPES:
        channel = await _get_agent_channel(db, agent_id=agent_id, channel_type=channel_type)
        if channel is None:
            raise ManagerDispatchError(
                f"Канал типа '{channel_type}' не найден у агента",
                http_status_code=400,
            )
        return await _dispatch_to_wappi_phone_channel(
            channel_type=channel_type,
            channel=channel,
            content=content,
            dialog_peer=dialog_peer,
            manager_user_id=manager_user_id,
        )

    raise ManagerDispatchError(
        f"Отправка менеджером не поддерживается для платформы '{channel_type}'",
        http_status_code=400,
    )
