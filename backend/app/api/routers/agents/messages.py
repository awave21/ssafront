from __future__ import annotations

import json
import os
import time
import structlog
import asyncio
from uuid import UUID
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.api.routers.runs import create_run, stream_run
from app.services.run_service import append_session_messages
from app.db.models.channel import AgentChannel, Channel
from app.db.models.run import Run
from app.db.models.session_message import SessionMessage
from app.db.session import get_db, async_session_factory
from app.schemas.auth import AuthContext
from app.schemas.dialog import MessageRead, MessageCreate, ManagerMessageCreate, StreamRequest
from app.schemas.run import RunCreate
from app.services.dialog_state import update_last_manager_message
from app.services.telegram import send_telegram_message, TelegramWebhookError
from app.utils.broadcast import broadcaster
from app.utils.message_mapping import build_manager_message

logger = structlog.get_logger(__name__)

router = APIRouter()

@router.get("/events")
async def agent_events(
    request: Request,
    agent_id: UUID,
    user: AuthContext = Depends(require_scope("dialogs:read")),
) -> EventSourceResponse:
    """
    SSE канал для получения ВСЕХ событий агента (новые сообщения из любых каналов).
    """
    # region agent log
    try:
        os.makedirs("/opt/app-agent/myapp/backend/.cursor", exist_ok=True)
        with open("/opt/app-agent/myapp/backend/.cursor/debug-e26c68.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "e26c68",
                "runId": "audit-1",
                "hypothesisId": "H1",
                "location": "app/api/routers/agents/messages.py:agent_events",
                "message": "agent_events_subscribe",
                "data": {
                    "agent_id": str(agent_id),
                    "tenant_id": str(user.tenant_id) if user else None,
                    "user_id": str(user.user_id) if user else None,
                    "scopes": list(user.scopes) if user and user.scopes else [],
                },
                "timestamp": int(time.time() * 1000),
            }) + "\n")
    except Exception:
        pass
    # endregion agent log
    async def event_generator():
        queue = await broadcaster.subscribe(agent_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                
                try:
                    # Ждем новое событие из шины
                    event = await asyncio.wait_for(queue.get(), timeout=20.0)
                    
                    event_type = event.get("type")
                    event_data = event.get("data", {})
                    
                    if event_type == "message_created":
                        # Маппим сообщение для фронтенда
                        msg_data = event_data.get("message", {})
                        msg_id = event_data.get("id")
                        session_id = event_data.get("session_id")
                        created_at_str = event_data.get("created_at")
                        created_at = datetime.fromisoformat(created_at_str) if created_at_str else datetime.utcnow()
                        
                        mapped_messages = _map_session_message(
                            msg_data, 
                            msg_id, 
                            created_at, 
                            session_id=session_id, 
                            agent_id=agent_id
                        )
                        
                        for m in mapped_messages:
                            yield {
                                "event": "message_created",
                                "data": m.model_dump_json()
                            }
                    
                    elif event_type == "dialog_updated":
                        yield {
                            "event": "dialog_updated",
                            "data": json.dumps(event_data)
                        }
                        
                except asyncio.TimeoutError:
                    # Пинг для поддержания соединения
                    yield {"event": "ping", "data": "keep-alive"}
        finally:
            await broadcaster.unsubscribe(agent_id, queue)

    return EventSourceResponse(event_generator())

def _map_session_message(msg_data: dict[str, Any], msg_id: UUID, created_at: datetime, session_id: str | None = None, agent_id: UUID | None = None) -> list[MessageRead]:
    """
    Маппинг системного сообщения pydantic-ai в список сообщений для фронтенда.
    """
    from app.utils.message_mapping import infer_role, extract_user_info, extract_text_contents

    mapped_role = infer_role(msg_data)
    user_info = extract_user_info(msg_data)
    contents = extract_text_contents(msg_data)

    return [
        MessageRead(
            id=msg_id,
            session_id=session_id,
            agent_id=agent_id,
            role=mapped_role,
            type="text",
            content=content,
            status="done",
            created_at=created_at,
            user_info=user_info,
        )
        for content in contents
    ]

@router.get("/debug/session/{session_id}")
async def debug_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    DEBUG: Получить сырые сообщения из session_messages для конкретной сессии.
    """
    # region agent log
    try:
        os.makedirs("/opt/app-agent/myapp/backend/.cursor", exist_ok=True)
        with open("/opt/app-agent/myapp/backend/.cursor/debug-e26c68.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "e26c68",
                "runId": "audit-1",
                "hypothesisId": "H2",
                "location": "app/api/routers/agents/messages.py:debug_session_messages",
                "message": "debug_session_messages_called",
                "data": {
                    "session_id": session_id,
                },
                "timestamp": int(time.time() * 1000),
            }) + "\n")
    except Exception:
        pass
    # endregion agent log
    stmt = select(SessionMessage).where(SessionMessage.session_id == session_id).order_by(SessionMessage.message_index.asc())
    result = await db.execute(stmt)
    msgs = result.scalars().all()
    
    return [
        {
            "id": str(m.id),
            "index": m.message_index,
            "run_id": str(m.run_id),
            "raw_message": m.message,
            "created_at": m.created_at.isoformat()
        }
        for m in msgs
    ]

@router.get("/{dialog_id}/messages")
async def list_messages(
    agent_id: UUID,
    dialog_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    before: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("dialogs:read")),
):
    """
    Загрузить историю сообщений для диалога.
    """
    # Проверяем доступ к агенту
    await get_agent_or_404(agent_id, db, user)
    # region agent log
    try:
        os.makedirs("/opt/app-agent/myapp/backend/.cursor", exist_ok=True)
        with open("/opt/app-agent/myapp/backend/.cursor/debug-e26c68.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "e26c68",
                "runId": "audit-1",
                "hypothesisId": "H1",
                "location": "app/api/routers/agents/messages.py:list_messages",
                "message": "list_messages_called",
                "data": {
                    "agent_id": str(agent_id),
                    "dialog_id": dialog_id,
                    "tenant_id": str(user.tenant_id) if user else None,
                    "limit": limit,
                    "before": str(before) if before else None,
                },
                "timestamp": int(time.time() * 1000),
            }) + "\n")
    except Exception:
        pass
    # endregion agent log

    logger.info("list_messages_request", session_id=dialog_id, agent_id=str(agent_id))

    stmt = (
        select(SessionMessage)
        .where(
            SessionMessage.session_id == dialog_id,
        )
        .order_by(SessionMessage.message_index.asc())
    )
    
    # Пагинация 'before' (для скролла вверх)
    if before:
        before_stmt = select(SessionMessage.message_index).where(SessionMessage.id == before)
        before_index = (await db.execute(before_stmt)).scalar()
        if before_index:
            stmt = stmt.where(SessionMessage.message_index < before_index)
    
    result = await db.execute(stmt)
    db_messages = result.scalars().all()
    
    logger.info("list_messages_found", count=len(db_messages))
    
    all_mapped = []
    for db_msg in db_messages:
        try:
            mapped = _map_session_message(
                db_msg.message, 
                db_msg.id, 
                db_msg.created_at,
                session_id=dialog_id,
                agent_id=agent_id
            )
            # Сериализуем каждое сообщение в словарь через Pydantic для консистентности
            all_mapped.extend([m.model_dump(mode='json') for m in mapped])
        except Exception as e:
            logger.error("map_message_error", error=str(e), msg_id=str(db_msg.id))
            continue
    
    # Если таблица session_messages пуста или не удалось распарсить контент,
    # используем fallback из таблицы runs (input_message / output_message).
    if not all_mapped:
        fallback_messages = []
        run_stmt = (
            select(Run)
            .where(
                Run.session_id == dialog_id,
                Run.agent_id == agent_id
            )
            .order_by(Run.created_at.asc())
        )
        run_result = await db.execute(run_stmt)
        runs = run_result.scalars().all()

        # User info (например, Telegram)
        user_info = {"session_id": dialog_id}
        if dialog_id.startswith("telegram:"):
            user_info["platform"] = "telegram"
            user_info["platform_id"] = dialog_id.split(":")[1]

        for run in runs:
            if run.input_message:
                fallback_messages.append({
                    "id": f"{run.id}:user",
                    "session_id": dialog_id,
                    "agent_id": str(agent_id),
                    "role": "user",
                    "type": "text",
                    "content": run.input_message,
                    "status": "done",
                    "created_at": run.created_at.isoformat(),
                    "user_info": user_info
                })
            if run.output_message:
                fallback_messages.append({
                    "id": f"{run.id}:agent",
                    "session_id": dialog_id,
                    "agent_id": str(agent_id),
                    "role": "agent",
                    "type": "text",
                    "content": run.output_message,
                    "status": "done",
                    "created_at": (run.updated_at or run.created_at).isoformat(),
                    "user_info": user_info
                })

        logger.info("list_messages_fallback_runs", count=len(fallback_messages))
        all_mapped = fallback_messages

    logger.info("list_messages_mapped", count=len(all_mapped))
    return {"messages": all_mapped[-limit:]}

@router.post("/{dialog_id}/messages", response_model=Any)
async def send_message(
    agent_id: UUID,
    dialog_id: str,
    payload: MessageCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("runs:write")),
) -> Any:
    """
    Отправить сообщение в диалог. 
    Использует существующий эндпоинт создания рана.
    """
    # Проверяем доступ к агенту
    await get_agent_or_404(agent_id, db, user)

    run_payload = RunCreate(
        agent_id=agent_id,
        session_id=dialog_id,
        input_message=payload.content
    )
    return await create_run(payload=run_payload, request=request, db=db, user=user)

@router.post("/{dialog_id}/messages/stream")
async def stream_message(
    agent_id: UUID,
    dialog_id: str,
    payload: StreamRequest,
    request: Request,
    user: AuthContext = Depends(require_scope("runs:write")),
) -> EventSourceResponse:
    """
    Стриминг ответа агента.
    """
    # Найдем последнее сообщение пользователя в сессии
    async with async_session_factory() as db:
        # Проверяем доступ к агенту
        await get_agent_or_404(agent_id, db, user)

        stmt = (
            select(Run.input_message)
            .where(
                Run.session_id == dialog_id,
                Run.agent_id == agent_id,
                # Run.tenant_id == user.tenant_id
            )
            .order_by(Run.created_at.desc())
            .limit(1)
        )
        last_input = (await db.execute(stmt)).scalar()
        if not last_input:
            raise HTTPException(status_code=404, detail="No messages found in dialog to stream response")

    run_payload = RunCreate(
        agent_id=agent_id,
        session_id=dialog_id,
        input_message=last_input
    )
    
    return await stream_run(payload=run_payload, request=request, user=user)


@router.post("/{dialog_id}/manager-message")
async def send_manager_message(
    agent_id: UUID,
    dialog_id: str,
    payload: ManagerMessageCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("dialogs:write")),
) -> dict[str, Any]:
    """
    Отправить сообщение от менеджера в диалог.

    1. Сохраняет сообщение в session_messages с ролью "manager".
    2. Отправляет сообщение пользователю в Telegram.
    3. Обновляет last_manager_message_at для автопаузы агента.
    """
    agent = await get_agent_or_404(agent_id, db, user)

    # --- Найти Telegram-канал агента для получения bot_token ---
    channel_stmt = (
        select(Channel)
        .join(AgentChannel, AgentChannel.channel_id == Channel.id)
        .where(
            AgentChannel.agent_id == agent_id,
            Channel.type == "telegram",
            Channel.is_deleted.is_(False),
        )
        .limit(1)
    )
    channel = (await db.execute(channel_stmt)).scalar_one_or_none()
    if not channel or not channel.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram channel not configured for this agent",
        )

    # --- Извлечь chat_id из dialog_id (формат: "telegram:306597938") ---
    if not dialog_id.startswith("telegram:"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manager messages are only supported for Telegram dialogs",
        )
    try:
        chat_id = int(dialog_id.split(":")[1])
    except (IndexError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid dialog_id format: {dialog_id}",
        )

    # --- Создать Run для менеджерского сообщения ---
    from uuid import uuid4

    trace_id = str(uuid4())
    run = Run(
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        session_id=dialog_id,
        status="succeeded",
        input_message=payload.content,
        trace_id=trace_id,
    )
    db.add(run)
    await db.flush()

    # --- Сохранить сообщение менеджера и броадкастить ---
    manager_msg = build_manager_message(payload.content)
    manager_user_info = {
        "platform": "manager",
        "session_id": dialog_id,
        "manager_user_id": str(user.user_id),
    }
    await append_session_messages(
        db,
        user.tenant_id,
        dialog_id,
        run.id,
        [manager_msg],
        agent.max_history_messages,
        agent_id=agent_id,
        user_info=manager_user_info,
    )

    run.updated_at = datetime.utcnow()
    await db.commit()

    # --- Обновить last_manager_message_at для автопаузы ---
    await update_last_manager_message(db, agent_id=agent_id, tenant_id=user.tenant_id, session_id=dialog_id)

    # --- Отправить в Telegram ---
    telegram_ok = True
    telegram_error = None
    try:
        await send_telegram_message(
            bot_token=channel.telegram_bot_token,
            chat_id=chat_id,
            text=payload.content,
        )
    except TelegramWebhookError as exc:
        telegram_ok = False
        telegram_error = str(exc)
        logger.warning(
            "manager_message_telegram_send_failed",
            chat_id=chat_id,
            agent_id=str(agent_id),
            error=str(exc),
        )

    logger.info(
        "manager_message_sent",
        agent_id=str(agent_id),
        dialog_id=dialog_id,
        chat_id=chat_id,
        telegram_ok=telegram_ok,
    )

    return {
        "ok": True,
        "message_id": str(run.id),
        "dialog_id": dialog_id,
        "telegram_sent": telegram_ok,
        "telegram_error": telegram_error,
    }

