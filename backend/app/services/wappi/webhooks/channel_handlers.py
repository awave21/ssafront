from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.channel import Channel
from app.services.wappi import build_wappi_client, resolve_wappi_async_timeout_range, resolve_wappi_max_bot_id
from app.services.wappi.webhooks.message_normalizer import (
    WAPPI_TELEGRAM_TEXT_EVENT_TYPES,
    WAPPI_WHATSAPP_TEXT_EVENT_TYPES,
    extract_text_body,
    is_from_linked_account,
    max_send_ids,
    max_user_info,
    max_wh_type_is_chat_message,
    platform_is_max,
    telegram_phone_user_info,
    telegram_reply_recipient,
    whatsapp_reply_recipient,
    whatsapp_send_recipient,
    whatsapp_user_info,
)
from app.services.wappi.webhooks.pipeline import (
    InboundMessageContext,
    WappiChannelStrategy,
    process_wappi_channel_messages,
)

logger = structlog.get_logger()


def _telegram_delivery_session_id(raw_msg: dict[str, Any]) -> str | None:
    chat_key = telegram_reply_recipient(raw_msg)
    if not chat_key:
        return None
    return f"telegram_phone:{chat_key}"


def _whatsapp_delivery_session_id(raw_msg: dict[str, Any]) -> str | None:
    chat_key = whatsapp_reply_recipient(raw_msg)
    if not chat_key:
        return None
    return f"whatsapp:{chat_key}"


def _max_delivery_session_id(raw_msg: dict[str, Any]) -> str | None:
    recipient, chat_peer = max_send_ids(raw_msg)
    from_raw = str(raw_msg.get("from") or "").strip()
    session_peer = chat_peer or recipient or from_raw
    if not session_peer:
        return None
    return f"max:{session_peer}"


def _build_telegram_context(
    raw_msg: dict[str, Any],
    channel: Channel,
    _agent_id: UUID,
) -> InboundMessageContext | None:
    chat_key = telegram_reply_recipient(raw_msg)
    input_text = extract_text_body(raw_msg)
    if not input_text or not chat_key:
        return None

    user_info = telegram_phone_user_info(raw_msg, chat_id_str=chat_key, channel=channel)
    from_id = str(raw_msg.get("from") or "").strip()
    platform_user_id = from_id or chat_key
    wh_type = str(raw_msg.get("wh_type") or "").strip().lower()
    linked_account_message = wh_type == "outgoing_message_phone" or is_from_linked_account(raw_msg)
    return InboundMessageContext(
        session_id=f"telegram_phone:{chat_key}",
        input_text=input_text,
        user_info=user_info,
        platform_user_id=platform_user_id,
        linked_account_message=linked_account_message,
        raw_msg=raw_msg,
        send_payload={"chat_key": chat_key},
    )


def _build_whatsapp_context(
    raw_msg: dict[str, Any],
    channel: Channel,
    _agent_id: UUID,
) -> InboundMessageContext | None:
    chat_key = whatsapp_reply_recipient(raw_msg)
    input_text = extract_text_body(raw_msg)
    if not input_text or not chat_key:
        return None

    user_info = whatsapp_user_info(raw_msg, session_peer=chat_key, channel=channel)
    from_id = str(raw_msg.get("from") or "").strip()
    platform_user_id = from_id or chat_key
    wh_type = str(raw_msg.get("wh_type") or "").strip().lower()
    linked_account_message = wh_type == "outgoing_message_phone" or is_from_linked_account(raw_msg)
    return InboundMessageContext(
        session_id=f"whatsapp:{chat_key}",
        input_text=input_text,
        user_info=user_info,
        platform_user_id=platform_user_id,
        linked_account_message=linked_account_message,
        raw_msg=raw_msg,
        send_payload={"chat_key": chat_key},
    )


def _build_max_context(
    raw_msg: dict[str, Any],
    channel: Channel,
    agent_id: UUID,
) -> InboundMessageContext | None:
    recipient, chat_peer = max_send_ids(raw_msg)
    from_raw = str(raw_msg.get("from") or "").strip()
    session_peer = chat_peer or recipient or from_raw
    input_text = extract_text_body(raw_msg)
    if not input_text:
        return None
    if not session_peer:
        logger.info(
            "wappi_max_message_skipped_no_peer",
            channel_id=str(channel.id),
            agent_id=str(agent_id),
        )
        return None

    user_info = max_user_info(raw_msg, session_peer=session_peer, channel=channel)
    platform_user_id = from_raw or recipient or session_peer
    wh_type = str(raw_msg.get("wh_type") or "").strip().lower()
    linked_account_message = wh_type == "outgoing_message_phone" or is_from_linked_account(raw_msg)
    return InboundMessageContext(
        session_id=f"max:{session_peer}",
        input_text=input_text,
        user_info=user_info,
        platform_user_id=platform_user_id,
        linked_account_message=linked_account_message,
        raw_msg=raw_msg,
        send_payload={"recipient": recipient, "chat_peer": chat_peer},
    )


def _telegram_platform_supported(raw_msg: dict[str, Any]) -> bool:
    return str(raw_msg.get("platform") or "").strip().lower() == "telegram"


def _whatsapp_platform_supported(raw_msg: dict[str, Any]) -> bool:
    platform_raw = str(raw_msg.get("platform") or "").strip().lower()
    if platform_raw and platform_raw not in {"whatsapp", "wa"}:
        return False
    return True


def _max_platform_supported(raw_msg: dict[str, Any]) -> bool:
    plat_raw = raw_msg.get("platform")
    if plat_raw is not None and str(plat_raw).strip():
        return platform_is_max(plat_raw)
    return True


async def _send_telegram_reply(
    channel: Channel,
    _agent_id: UUID,
    reply_text: str,
    context: InboundMessageContext,
) -> None:
    profile_id = str(channel.wappi_profile_id or "").strip()
    chat_key = str(context.send_payload.get("chat_key") or "").strip()
    if not profile_id or not chat_key:
        return

    client = build_wappi_client()
    timeout_from, timeout_to = resolve_wappi_async_timeout_range()
    await client.send_telegram_async_message(
        profile_id=profile_id,
        body=reply_text,
        recipient=chat_key,
        timeout_from=timeout_from,
        timeout_to=timeout_to,
    )


async def _send_whatsapp_reply(
    channel: Channel,
    agent_id: UUID,
    reply_text: str,
    context: InboundMessageContext,
) -> None:
    profile_id = str(channel.wappi_profile_id or "").strip()
    chat_key = str(context.send_payload.get("chat_key") or "").strip()
    if not profile_id or not chat_key:
        return

    recipient_for_send = whatsapp_send_recipient(chat_key)
    if not recipient_for_send:
        logger.warning(
            "wappi_whatsapp_send_reply_skipped_missing_recipient",
            channel_id=str(channel.id),
            agent_id=str(agent_id),
            session_id=context.session_id,
            chat_key=chat_key,
        )
        return

    client = build_wappi_client()
    timeout_from, timeout_to = resolve_wappi_async_timeout_range()
    await client.send_whatsapp_async_message(
        profile_id=profile_id,
        body=reply_text,
        recipient=recipient_for_send,
        timeout_from=timeout_from,
        timeout_to=timeout_to,
    )


async def _send_max_reply(
    channel: Channel,
    agent_id: UUID,
    reply_text: str,
    context: InboundMessageContext,
) -> None:
    profile_id = str(channel.wappi_profile_id or "").strip()
    if not profile_id:
        return

    recipient = context.send_payload.get("recipient")
    chat_peer = context.send_payload.get("chat_peer")
    bot_id = (resolve_wappi_max_bot_id(channel) or "").strip()
    if not bot_id or (not recipient and not chat_peer):
        logger.warning(
            "wappi_max_send_reply_skipped_missing_params",
            channel_id=str(channel.id),
            agent_id=str(agent_id),
            has_bot_id=bool(bot_id),
            has_recipient=bool(recipient),
            has_chat_id=bool(chat_peer),
        )
        return

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


_CHANNEL_STRATEGIES: dict[str, WappiChannelStrategy] = {
    "telegram_phone": WappiChannelStrategy(
        channel_type="telegram_phone",
        user_disabled_platform="telegram_phone",
        run_log_source="wappi_telegram_phone",
        operator_log_source="wappi_telegram_phone_operator",
        delivery_not_found_event="wappi_telegram_phone_delivery_status_message_not_found",
        delivery_update_failed_event="wappi_telegram_phone_delivery_status_update_failed",
        operator_message_failed_event="wappi_telegram_phone_operator_message_failed",
        message_skipped_event="wappi_telegram_phone_message_skipped",
        save_without_agent_failed_event="wappi_telegram_phone_save_without_agent_failed",
        send_reply_failed_event="wappi_telegram_send_reply_failed",
        is_text_event=lambda wh_type: wh_type in WAPPI_TELEGRAM_TEXT_EVENT_TYPES,
        is_platform_supported=_telegram_platform_supported,
        resolve_delivery_session_id=_telegram_delivery_session_id,
        build_inbound_context=_build_telegram_context,
        send_reply=_send_telegram_reply,
    ),
    "whatsapp": WappiChannelStrategy(
        channel_type="whatsapp",
        user_disabled_platform="whatsapp",
        run_log_source="wappi_whatsapp",
        operator_log_source="wappi_whatsapp_operator",
        delivery_not_found_event="wappi_whatsapp_delivery_status_message_not_found",
        delivery_update_failed_event="wappi_whatsapp_delivery_status_update_failed",
        operator_message_failed_event="wappi_whatsapp_operator_message_failed",
        message_skipped_event="wappi_whatsapp_message_skipped",
        save_without_agent_failed_event="wappi_whatsapp_save_without_agent_failed",
        send_reply_failed_event="wappi_whatsapp_send_reply_failed",
        is_text_event=lambda wh_type: wh_type in WAPPI_WHATSAPP_TEXT_EVENT_TYPES,
        is_platform_supported=_whatsapp_platform_supported,
        resolve_delivery_session_id=_whatsapp_delivery_session_id,
        build_inbound_context=_build_whatsapp_context,
        send_reply=_send_whatsapp_reply,
    ),
    "max": WappiChannelStrategy(
        channel_type="max",
        user_disabled_platform="max",
        run_log_source="wappi_max",
        operator_log_source="wappi_max_operator",
        delivery_not_found_event="wappi_max_delivery_status_message_not_found",
        delivery_update_failed_event="wappi_max_delivery_status_update_failed",
        operator_message_failed_event="wappi_max_operator_message_failed",
        message_skipped_event="wappi_max_message_skipped",
        save_without_agent_failed_event="wappi_max_save_without_agent_failed",
        send_reply_failed_event="wappi_max_send_reply_failed",
        is_text_event=max_wh_type_is_chat_message,
        is_platform_supported=_max_platform_supported,
        resolve_delivery_session_id=_max_delivery_session_id,
        build_inbound_context=_build_max_context,
        send_reply=_send_max_reply,
    ),
}


async def handle_wappi_channel_messages(
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

    strategy = _CHANNEL_STRATEGIES.get(channel.type)
    if strategy is None:
        return
    await process_wappi_channel_messages(
        db,
        channel=channel,
        agent_id=agent_id,
        agent=agent,
        parsed_json=parsed_json,
        strategy=strategy,
    )
