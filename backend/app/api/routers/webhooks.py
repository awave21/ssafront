from __future__ import annotations

import asyncio
import json
import secrets
import structlog
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.channel import AgentChannel, Channel
from app.db.session import get_db
from app.api.routers.webhooks_inbound_agent import process_webhook_inbound_agent_message
from app.api.routers.webhooks_phone import router as phone_webhooks_router
from app.api.routers.webhooks_utils import mask_headers, sanitize_agent_reply_text
from app.services.dialog_state import is_dialog_active, is_manager_paused, set_dialog_status
from app.services.agent_user_state import is_agent_user_disabled
from app.services.telegram import send_telegram_chat_action, send_telegram_message, TelegramWebhookError

logger = structlog.get_logger()
webhook_logger = structlog.get_logger("webhooks")

router = APIRouter()


_TELEGRAM_INTEGRATION_LABELS: dict[str, str] = {
    "telegram": "Telegram бот",
}
_TELEGRAM_PRIVATE_CHAT_TYPES = {"private", "user", "dialog", "direct", "dm", "personal"}
_TELEGRAM_BLOCKED_CHAT_TYPES = {"group", "supergroup", "channel", "chat", "megagroup"}


def _parse_telegram_message(body: dict[str, Any]) -> tuple[int, str, dict[str, Any]] | None:
    """Извлечь chat_id, text и user_info из update. Возвращает (chat_id, text, user_info) или None."""
    msg = body.get("message") or body.get("edited_message")
    if not isinstance(msg, dict):
        return None
    chat = msg.get("chat")
    if not isinstance(chat, dict):
        return None
    chat_id = chat.get("id")
    if chat_id is None or not isinstance(chat_id, (int, float)):
        return None
    chat_id_int = int(chat_id)

    from_user = msg.get("from")
    if not isinstance(from_user, dict):
        return None
    is_bot_raw = from_user.get("is_bot")
    if is_bot_raw is True:
        return None
    if isinstance(is_bot_raw, str) and is_bot_raw.strip().lower() in {"true", "1", "yes"}:
        return None

    chat_type = str(chat.get("type") or "").strip().lower()
    if chat_type in _TELEGRAM_BLOCKED_CHAT_TYPES:
        return None

    # Разрешаем только личные чаты: либо явно private, либо совпадение chat.id и from.id.
    is_private_chat = chat_type in _TELEGRAM_PRIVATE_CHAT_TYPES
    from_id_raw = from_user.get("id")
    from_id_int: int | None = int(from_id_raw) if isinstance(from_id_raw, (int, float)) else None
    if from_id_int is not None and from_id_int == chat_id_int:
        is_private_chat = True
    if not is_private_chat:
        return None

    text = msg.get("text")
    if not text or not isinstance(text, str):
        return None

    platform_user_id = str(from_id_int) if from_id_int is not None else str(chat_id_int)
    channel_label = _TELEGRAM_INTEGRATION_LABELS["telegram"]
    user_info: dict[str, Any] = {
        "platform": "telegram",
        "platform_id": platform_user_id,
        "integration_channel_type": "telegram",
        "integration_channel_label": channel_label,
        "message_sender_kind": "contact",
        "sender_display_label": f"Клиент ({channel_label})",
    }
    if isinstance(from_user.get("username"), str) and from_user["username"].strip():
        user_info["username"] = from_user["username"].strip()
    if isinstance(from_user.get("first_name"), str) and from_user["first_name"].strip():
        user_info["first_name"] = from_user["first_name"].strip()
    if isinstance(from_user.get("last_name"), str) and from_user["last_name"].strip():
        user_info["last_name"] = from_user["last_name"].strip()

    return chat_id_int, text.strip(), user_info


def _parse_my_chat_member(body: dict[str, Any]) -> tuple[int, str] | None:
    """
    Парсинг my_chat_member update от Telegram.

    Приходит когда пользователь блокирует/разблокирует бота.
    Возвращает (chat_id, new_status) где new_status — это статус бота в чате:
      - "kicked" / "left" → пользователь заблокировал бота
      - "member" → пользователь разблокировал бота
    """
    update = body.get("my_chat_member")
    if not isinstance(update, dict):
        return None
    chat = update.get("chat")
    if not isinstance(chat, dict):
        return None
    chat_id = chat.get("id")
    if chat_id is None or not isinstance(chat_id, (int, float)):
        return None
    new_member = update.get("new_chat_member")
    if not isinstance(new_member, dict):
        return None
    member_status = new_member.get("status")
    if not member_status or not isinstance(member_status, str):
        return None
    return int(chat_id), member_status


async def _process_telegram_message(
    db: AsyncSession,
    agent: Agent,
    channel: Channel,
    chat_id: int,
    input_text: str,
    user_info: dict[str, Any] | None = None,
    run_agent: bool = True,
) -> str | None:
    """Запустить агента и вернуть ответ. Возвращает None при ошибке."""
    session_id = f"telegram:{chat_id}"
    channel_label = _TELEGRAM_INTEGRATION_LABELS["telegram"]
    base = user_info or {
        "platform": "telegram",
        "platform_id": str(chat_id),
        "integration_channel_type": "telegram",
        "integration_channel_label": channel_label,
        "message_sender_kind": "contact",
        "sender_display_label": f"Клиент ({channel_label})",
    }
    return await process_webhook_inbound_agent_message(
        db,
        agent,
        session_id=session_id,
        input_text=input_text,
        user_info=base,
        run_agent=run_agent,
        log_source="telegram_bot",
        telegram_debug_audit=True,
    )


@router.post("/webhooks/telegram/{webhook_token}")
async def telegram_webhook(
    webhook_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    stmt = (
        select(Channel, AgentChannel.agent_id, Agent)
        .join(AgentChannel, AgentChannel.channel_id == Channel.id)
        .join(Agent, Agent.id == AgentChannel.agent_id)
        .where(
            Channel.telegram_webhook_token == webhook_token,
            Channel.is_deleted.is_(False),
            Agent.is_deleted.is_(False),
        )
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    channel, agent_id, agent = row
    if channel.type != "telegram":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Channel is not telegram")
    if not channel.telegram_webhook_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Webhook is not enabled")

    expected_secret = channel.telegram_webhook_secret
    if expected_secret:
        provided_secret = request.headers.get("x-telegram-bot-api-secret-token")
        if not provided_secret or not secrets.compare_digest(provided_secret, expected_secret):
            logger.warning(
                "telegram_webhook_secret_invalid",
                channel_id=str(channel.id),
                agent_id=str(agent_id),
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook secret",
            )

    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8", errors="replace")
    parsed_json: dict[str, Any] | None = None
    if raw_body:
        try:
            parsed_json = json.loads(raw_body)
        except Exception:
            parsed_json = None

    log_payload: dict[str, Any] = {
        "channel_id": str(channel.id),
        "agent_id": str(agent_id),
        "method": request.method,
        "path": str(request.url.path),
        "query_params": dict(request.query_params),
        "headers": mask_headers(dict(request.headers)),
        "body_raw": raw_text,
        "body_json": parsed_json,
        "client_ip": request.client.host if request.client else "unknown",
    }
    logger.info(
        "telegram_webhook_received",
        **log_payload,
    )
    webhook_logger.info(
        "telegram_webhook_incoming",
        **log_payload,
    )

    body = parsed_json or {}

    # --- 1. Обработка my_chat_member (блокировка/разблокировка бота) ---
    member_update = _parse_my_chat_member(body)
    if member_update is not None:
        member_chat_id, member_status = member_update
        session_id = f"telegram:{member_chat_id}"

        if member_status in ("kicked", "left"):
            # Пользователь заблокировал бота → отключаем агента ТОЛЬКО для этого чата
            await set_dialog_status(
                db, agent_id=agent_id, tenant_id=agent.tenant_id,
                session_id=session_id, new_status="disabled",
            )
            logger.info(
                "telegram_bot_blocked",
                chat_id=member_chat_id,
                agent_id=str(agent_id),
                session_id=session_id,
            )
        elif member_status == "member":
            # Пользователь разблокировал бота → включаем агента обратно
            await set_dialog_status(
                db, agent_id=agent_id, tenant_id=agent.tenant_id,
                session_id=session_id, new_status="active",
            )
            logger.info(
                "telegram_bot_unblocked",
                chat_id=member_chat_id,
                agent_id=str(agent_id),
                session_id=session_id,
            )

        return {"ok": True}

    # --- 2. Обработка входящего сообщения и ответ агентом ---
    parsed = _parse_telegram_message(body)
    if parsed:
        chat_id, input_text, user_info = parsed
        session_id = f"telegram:{chat_id}"

        # Проверяем, не отключён ли агент для этого конкретного чата
        dialog_active = await is_dialog_active(db, agent_id, session_id)

        # Проверяем автопаузу менеджера (менеджер недавно писал в этот чат)
        manager_paused = False
        if dialog_active:
            manager_paused = await is_manager_paused(db, agent_id, session_id)

        user_disabled = await is_agent_user_disabled(
            db,
            tenant_id=agent.tenant_id,
            agent_id=agent_id,
            platform="telegram",
            platform_user_id=str(chat_id),
        )

        bot_token = channel.telegram_bot_token
        should_run_agent = dialog_active and not manager_paused and not agent.is_disabled and not user_disabled

        if should_run_agent and bot_token and input_text:
            stop_typing = asyncio.Event()

            async def keep_typing() -> None:
                while not stop_typing.is_set():
                    await send_telegram_chat_action(bot_token=bot_token, chat_id=chat_id, action="typing")
                    try:
                        await asyncio.wait_for(stop_typing.wait(), timeout=4.0)
                    except asyncio.TimeoutError:
                        continue

            typing_task = asyncio.create_task(keep_typing())
            try:
                reply = await _process_telegram_message(
                    db, agent, channel, chat_id, input_text, user_info, run_agent=True
                )
            finally:
                stop_typing.set()
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass

            if reply and bot_token:
                reply_text = sanitize_agent_reply_text(reply)
                if reply_text:
                    sent = False
                    try:
                        await send_telegram_message(
                            bot_token=bot_token,
                            chat_id=chat_id,
                            text=reply_text,
                            parse_mode="Markdown",
                        )
                        sent = True
                    except TelegramWebhookError:
                        try:
                            await send_telegram_message(
                                bot_token=bot_token,
                                chat_id=chat_id,
                                text=reply_text,
                            )
                            sent = True
                        except TelegramWebhookError as exc:
                            logger.warning(
                                "telegram_send_reply_failed",
                                chat_id=chat_id,
                                agent_id=str(agent_id),
                                error=str(exc),
                            )
                            webhook_logger.warning(
                                "telegram_send_reply_failed",
                                chat_id=chat_id,
                                agent_id=str(agent_id),
                                session_id=session_id,
                                error=str(exc),
                            )
                    if sent:
                        webhook_logger.info(
                            "telegram_reply_sent",
                            chat_id=chat_id,
                            agent_id=str(agent_id),
                            session_id=session_id,
                            reply_len=len(reply_text),
                        )
                else:
                    logger.warning(
                        "telegram_agent_reply_empty_after_sanitize",
                        chat_id=chat_id,
                        agent_id=str(agent_id),
                        session_id=session_id,
                        raw_reply_len=len(reply) if isinstance(reply, str) else None,
                    )
                    webhook_logger.warning(
                        "telegram_agent_reply_empty_after_sanitize",
                        chat_id=chat_id,
                        agent_id=str(agent_id),
                        session_id=session_id,
                        raw_reply_len=len(reply) if isinstance(reply, str) else None,
                    )
            elif bot_token:
                logger.warning(
                    "telegram_agent_reply_empty",
                    chat_id=chat_id,
                    agent_id=str(agent_id),
                    session_id=session_id,
                )
                webhook_logger.warning(
                    "telegram_agent_reply_empty",
                    chat_id=chat_id,
                    agent_id=str(agent_id),
                    session_id=session_id,
                )
        else:
            # Агент не запускается: политика чата / канал / пауза.
            # Важно: раньше при отсутствии bot_token попадали в ветку с reason=dialog_inactive — это вводило в заблуждение.
            if agent.is_disabled:
                skip_reason = "agent_disabled"
            elif user_disabled:
                skip_reason = "agent_user_disabled"
            elif manager_paused:
                skip_reason = "manager_paused"
            elif not dialog_active:
                skip_reason = "dialog_inactive"
            elif not (bot_token and str(bot_token).strip()):
                skip_reason = "missing_bot_token"
            elif not (input_text and str(input_text).strip()):
                skip_reason = "empty_message"
            else:
                skip_reason = "unknown_skip"
            logger.info(
                "telegram_message_skipped",
                reason=skip_reason,
                chat_id=chat_id,
                agent_id=str(agent_id),
                session_id=session_id,
            )
            webhook_logger.info(
                "telegram_message_skipped",
                reason=skip_reason,
                chat_id=chat_id,
                agent_id=str(agent_id),
                session_id=session_id,
            )
            try:
                await _process_telegram_message(
                    db, agent, channel, chat_id, input_text, user_info, run_agent=False
                )
            except Exception as exc:
                logger.exception(
                    "telegram_save_without_agent_failed",
                    reason=skip_reason,
                    chat_id=chat_id,
                    agent_id=str(agent_id),
                    error=str(exc),
                )

    return {"ok": True}


router.include_router(phone_webhooks_router)
