from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import structlog
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.channel import AgentChannel, Channel
from app.db.models.run import Run
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.api.routers.webhooks_phone import router as phone_webhooks_router
from app.api.routers.webhooks_utils import mask_headers
from app.services.dialog_state import is_dialog_active, is_manager_paused, set_dialog_status
from app.services.agent_user_state import is_agent_user_disabled
from app.services.telegram import send_telegram_chat_action, send_telegram_message, TelegramWebhookError
from app.services.tool_executor import ToolExecutionError
from app.utils.message_mapping import build_user_prompt, filter_user_prompts

logger = structlog.get_logger()
webhook_logger = structlog.get_logger("webhooks")

router = APIRouter()


def _sanitize_reply(text: str) -> str:
    """Убрать технические параметры и repr-строки, заменить \\n на переносы строк."""
    if not text or not isinstance(text, str):
        return ""
    # AgentRunResult(output='...') -> только содержимое
    m = re.match(r"^AgentRunResult\(output=['\"](.+)['\"]\)\s*$", text.strip(), re.DOTALL)
    if m:
        text = m.group(1)
    elif text.strip().startswith("AgentRunResult("):
        inner = re.search(r"output=['\"](.+?)['\"]\)\s*$", text, re.DOTALL)
        if inner:
            text = inner.group(1)
    # Заменить литеральные \n и \t на реальные переносы и табуляцию
    text = text.replace("\\n", "\n").replace("\\t", "\t")
    return text


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
    text = msg.get("text")
    if not text or not isinstance(text, str):
        return None
    
    # Извлекаем информацию о пользователе из поля "from"
    from_user = msg.get("from") or {}
    user_info: dict[str, Any] = {
        "platform": "telegram",
        "platform_id": str(chat_id),
    }
    if from_user.get("username"):
        user_info["username"] = from_user["username"]
    if from_user.get("first_name"):
        user_info["first_name"] = from_user["first_name"]
    if from_user.get("last_name"):
        user_info["last_name"] = from_user["last_name"]
    
    return int(chat_id), text.strip(), user_info


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
    from app.services.logfire_cost_reconcile import schedule_logfire_cost_reconcile
    from app.services.run_service import (
        append_session_messages,
        execute_agent_run,
        get_session_history,
        load_agent_and_tools,
    )

    session_id = f"telegram:{chat_id}"

    # Подготовим user_info для передачи в broadcast (копия, чтобы не мутировать входной dict)
    base = user_info or {"platform": "telegram", "platform_id": str(chat_id)}
    telegram_user_info = {**base, "session_id": session_id}

    webhook_user = AuthContext(
        user_id=agent.owner_user_id,
        tenant_id=agent.tenant_id,
        scopes=["tools:write"],
    )
    # region agent log
    try:
        os.makedirs("/opt/app-agent/myapp/backend/.cursor", exist_ok=True)
        with open("/opt/app-agent/myapp/backend/.cursor/debug-e26c68.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "e26c68",
                "runId": "audit-1",
                "hypothesisId": "H4",
                "location": "app/api/routers/webhooks.py:_process_telegram_message",
                "message": "telegram_webhook_auth_context",
                "data": {
                    "agent_id": str(agent.id),
                    "tenant_id": str(agent.tenant_id),
                    "session_id": session_id,
                    "scopes": list(webhook_user.scopes),
                },
                "timestamp": int(time.time() * 1000),
            }) + "\n")
    except Exception:
        pass
    # endregion agent log

    trace_id = str(uuid4())
    run = Run(
        tenant_id=agent.tenant_id,
        agent_id=agent.id,
        session_id=session_id,
        status="running",
        input_message=input_text,
        trace_id=trace_id,
    )
    db.add(run)
    await db.flush()

    try:
        # Сразу сохраняем и броадкастим сообщение пользователя
        user_message = build_user_prompt(input_text)
        await append_session_messages(
            db,
            agent.tenant_id,
            session_id,
            run.id,
            [user_message],
            agent.max_history_messages,
            agent_id=agent.id,
            user_info=telegram_user_info,
        )
        await db.commit()

        if not run_agent:
            run.status = "succeeded"
            run.output_message = None
            run.messages = []
            run.prompt_tokens = 0
            run.completion_tokens = 0
            run.total_tokens = 0
            run.cost_usd = None
            run.cost_rub = None
            run.logfire_reconcile_status = "skipped"
            run.logfire_reconcile_error = "run_not_executed"
            run.tools_called = []
            return None

        agent_obj, tools, bindings = await load_agent_and_tools(
            db, agent.id, agent.tenant_id
        )
        message_history = await get_session_history(
            db, session_id, agent.tenant_id, agent.id, limit=agent.max_history_messages
        )

        result = await execute_agent_run(
            db,
            agent=agent_obj,
            tools=tools,
            bindings=bindings,
            run=run,
            input_message=input_text,
            trace_id=trace_id,
            user=webhook_user,
            session_id=session_id,
            message_history=message_history,
            new_messages_filter=filter_user_prompts,
            user_info=telegram_user_info,
        )
        schedule_logfire_cost_reconcile(run_id=run.id, trace_id=trace_id)
        return result.output
    except ToolExecutionError as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.logfire_reconcile_status = "skipped"
        run.logfire_reconcile_error = "run_failed"
        return "Произошла ошибка при выполнении запроса. Попробуйте ещё раз."
    except Exception as exc:  # noqa: BLE001
        logger.exception("telegram_webhook_agent_failed", trace_id=trace_id, error=str(exc))
        run.status = "failed"
        run.error_message = f"Runtime error: {str(exc)}"
        run.logfire_reconcile_status = "skipped"
        run.logfire_reconcile_error = "run_failed"
        return "Произошла ошибка при обработке сообщения. Попробуйте позже."
    finally:
        run.updated_at = datetime.utcnow()
        await db.commit()


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
                reply_text = _sanitize_reply(reply)
                if reply_text:
                    try:
                        await send_telegram_message(
                            bot_token=bot_token,
                            chat_id=chat_id,
                            text=reply_text,
                            parse_mode="Markdown",
                        )
                    except TelegramWebhookError:
                        try:
                            await send_telegram_message(
                                bot_token=bot_token,
                                chat_id=chat_id,
                                text=reply_text,
                            )
                        except TelegramWebhookError as exc:
                            logger.warning(
                                "telegram_send_reply_failed",
                                chat_id=chat_id,
                                agent_id=str(agent_id),
                                error=str(exc),
                            )
        else:
            # Агент не запускается: диалог неактивен ИЛИ менеджер на паузе.
            # Сохраняем сообщение пользователя без ответа агента.
            if agent.is_disabled:
                skip_reason = "agent_disabled"
            elif user_disabled:
                skip_reason = "agent_user_disabled"
            elif manager_paused:
                skip_reason = "manager_paused"
            else:
                skip_reason = "dialog_inactive"
            logger.info(
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
