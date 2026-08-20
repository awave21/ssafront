"""Jivo Bot API — входящий вебхук.

Jivo POST-ит события клиента на /webhooks/jivo/{token}. Мы находим канал по токену,
дедупим по event.id, мгновенно отвечаем 200, а обработку агентом и отправку ответа
(BOT_MESSAGE) делаем в фоне после debounce — Jivo ждёт вебхук лишь 3 сек.
"""

from __future__ import annotations

import json
import secrets
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.webhooks_inbound_agent import process_webhook_inbound_agent_message
from app.api.routers.webhooks_utils import mask_headers, sanitize_agent_reply_text
from app.db.models.agent import Agent
from app.db.models.channel import AgentChannel, Channel
from app.db.session import async_session_factory, get_db
from app.services.agent_user_state import is_agent_user_disabled
from app.services.dialog_state import is_dialog_active, is_manager_paused
from app.services.jivo import (
    JivoClientError,
    claim_event,
    is_outbound_configured,
    send_bot_message,
)
from app.services.message_debounce import debounce_and_run

logger = structlog.get_logger()
webhook_logger = structlog.get_logger("webhooks.jivo")

router = APIRouter()

_JIVO_CHANNEL_LABEL = "Jivo"


def _parse_jivo_client_message(
    body: dict[str, Any],
) -> tuple[str, str, str, str | None, dict[str, Any]] | None:
    """Извлечь (client_id, chat_id, text, site_id, user_info) из события CLIENT_MESSAGE.

    Возвращает None для не-текстовых / служебных событий (INVITE_AGENT, CHAT_CLOSED и т.п.).
    """
    if str(body.get("event") or "").upper() != "CLIENT_MESSAGE":
        return None

    message = body.get("message")
    if not isinstance(message, dict):
        return None
    if str(message.get("type") or "").upper() != "TEXT":
        return None
    text = message.get("text")
    if not text or not isinstance(text, str) or not text.strip():
        return None

    client_id = body.get("client_id")
    chat_id = body.get("chat_id")
    if client_id is None or chat_id is None:
        return None
    client_id = str(client_id).strip()
    chat_id = str(chat_id).strip()
    if not client_id or not chat_id:
        return None

    site_id = body.get("site_id")
    site_id = str(site_id).strip() if site_id is not None else None

    user_info: dict[str, Any] = {
        "platform": "jivo",
        "platform_id": client_id,
        "integration_channel_type": "jivo",
        "integration_channel_label": _JIVO_CHANNEL_LABEL,
        "message_sender_kind": "contact",
        "sender_display_label": f"Клиент ({_JIVO_CHANNEL_LABEL})",
        # chat_id меняется от чата к чату — сохраняем его, чтобы менеджер мог
        # ответить в актуальный чат Jivo (см. manager_dispatcher._dispatch_to_jivo).
        "jivo_chat_id": chat_id,
        "jivo_site_id": site_id,
    }
    sender = body.get("sender")
    if isinstance(sender, dict):
        name = sender.get("name")
        if isinstance(name, str) and name.strip():
            user_info["first_name"] = name.strip()
        page_url = sender.get("url")
        if isinstance(page_url, str) and page_url.strip():
            user_info["source_url"] = page_url.strip()

    return client_id, chat_id, text.strip(), site_id, user_info


@router.post("/webhooks/jivo/{token}")
async def jivo_webhook(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    stmt = (
        select(Channel, AgentChannel.agent_id, Agent)
        .join(AgentChannel, AgentChannel.channel_id == Channel.id)
        .join(Agent, Agent.id == AgentChannel.agent_id)
        .where(
            Channel.jivo_provider_token == token,
            Channel.is_deleted.is_(False),
            Agent.is_deleted.is_(False),
        )
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    channel, agent_id, agent = row
    if channel.type != "jivo":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Channel is not jivo")

    # Токен уже проверен через уникальный lookup, но сравним ещё раз константным временем.
    if not secrets.compare_digest(str(channel.jivo_provider_token or ""), token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    raw_body = await request.body()
    parsed_json: dict[str, Any] | None = None
    if raw_body:
        try:
            loaded = json.loads(raw_body)
            parsed_json = loaded if isinstance(loaded, dict) else None
        except Exception:
            parsed_json = None

    webhook_logger.info(
        "jivo_webhook_incoming",
        channel_id=str(channel.id),
        agent_id=str(agent_id),
        headers=mask_headers(dict(request.headers)),
        body_json=parsed_json,
        client_ip=request.client.host if request.client else "unknown",
    )

    body = parsed_json or {}
    parsed = _parse_jivo_client_message(body)
    if parsed is None:
        # Служебное/не-текстовое событие — принимаем, но не запускаем агента.
        return {"ok": True}

    client_id, chat_id, input_text, site_id, user_info = parsed

    # Дедуп: Jivo повторяет доставку при таймауте (до 2 ретраев).
    event_id = str(body.get("id") or "").strip()
    if not await claim_event(event_id):
        webhook_logger.info(
            "jivo_webhook_duplicate_skipped",
            channel_id=str(channel.id),
            agent_id=str(agent_id),
            event_id=event_id,
        )
        return {"ok": True}

    session_id = f"jivo:{client_id}"

    dialog_active = await is_dialog_active(db, agent_id, session_id)
    manager_paused = False
    if dialog_active:
        manager_paused = await is_manager_paused(db, agent_id, session_id)
    user_disabled = await is_agent_user_disabled(
        db,
        tenant_id=agent.tenant_id,
        agent_id=agent_id,
        platform="jivo",
        platform_user_id=client_id,
    )

    should_run_agent = (
        dialog_active and not manager_paused and not agent.is_disabled and not user_disabled
    )

    if not should_run_agent:
        # Сохранить сообщение клиента в диалог без запуска агента (пауза/политика).
        try:
            await process_webhook_inbound_agent_message(
                db,
                agent,
                session_id=session_id,
                input_text=input_text,
                user_info=user_info,
                run_agent=False,
                log_source="jivo",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "jivo_save_without_agent_failed",
                channel_id=str(channel.id),
                agent_id=str(agent_id),
                error=str(exc),
            )
        return {"ok": True}

    _channel_id = channel.id
    _agent_id_str = str(agent_id)
    _client_id = client_id
    _chat_id = chat_id

    async def _run_agent_after_debounce(
        aggregated_text: str, _message_ids: list[str] | None = None
    ) -> None:
        async with async_session_factory() as _db:
            stmt_inner = (
                select(Channel, Agent)
                .join(AgentChannel, AgentChannel.channel_id == Channel.id)
                .join(Agent, Agent.id == AgentChannel.agent_id)
                .where(Channel.id == _channel_id)
            )
            inner_row = (await _db.execute(stmt_inner)).first()
            if inner_row is None:
                return
            _channel, _agent = inner_row

            reply = await process_webhook_inbound_agent_message(
                _db,
                _agent,
                session_id=session_id,
                input_text=aggregated_text,
                user_info=user_info,
                run_agent=True,
                log_source="jivo",
            )

            reply_base_url = _channel.jivo_reply_base_url
            provider_id = _channel.jivo_provider_id
            provider_token = _channel.jivo_provider_token

        if not reply:
            webhook_logger.warning(
                "jivo_agent_reply_empty",
                channel_id=str(_channel_id),
                agent_id=_agent_id_str,
                session_id=session_id,
            )
            return

        reply_text = sanitize_agent_reply_text(reply)
        if not reply_text:
            return

        if not is_outbound_configured(reply_base_url, provider_id):
            # Канал ещё не достроен (клиент не ввёл ID провайдера / путь к ответу).
            webhook_logger.warning(
                "jivo_outbound_not_configured",
                channel_id=str(_channel_id),
                agent_id=_agent_id_str,
                session_id=session_id,
            )
            return

        try:
            await send_bot_message(
                reply_base_url=reply_base_url or "",
                provider_id=provider_id or "",
                token=provider_token or "",
                client_id=_client_id,
                chat_id=_chat_id,
                text=reply_text,
            )
            webhook_logger.info(
                "jivo_reply_sent",
                channel_id=str(_channel_id),
                agent_id=_agent_id_str,
                session_id=session_id,
                reply_len=len(reply_text),
            )
        except JivoClientError as exc:
            webhook_logger.warning(
                "jivo_send_reply_failed",
                channel_id=str(_channel_id),
                agent_id=_agent_id_str,
                session_id=session_id,
                error=str(exc),
            )

    debounce_delay = float(agent.debounce_delay_seconds) if agent.debounce_enabled else 0.0
    await debounce_and_run(
        session_id,
        input_text,
        _run_agent_after_debounce,
        message_id=event_id or None,
        delay=debounce_delay,
    )
    return {"ok": True}
