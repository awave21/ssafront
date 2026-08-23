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
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.api.routers.runs import create_run, stream_run
from app.services.run_service import append_session_messages
from app.db.models.run import Run
from app.db.models.session_message import SessionMessage
from app.db.models.tool_call_log import ToolCallLog
from app.db.session import get_db, async_session_factory
from app.schemas.auth import AuthContext
from app.schemas.dialog import MessageRead, MessageCreate, ManagerMessageCreate, StreamRequest
from app.schemas.run import RunCreate
from app.services.dialog_state import update_last_manager_message
from app.services.function_rules_runtime import run_rules_for_phase
from app.services.outbound import ManagerDispatchError, dispatch_manager_message
from app.utils.broadcast import broadcaster
from app.utils.message_mapping import build_manager_message
from uuid import uuid4 as _uuid4_for_trace

logger = structlog.get_logger(__name__)

router = APIRouter()

_MESSAGE_STATUS_ALIASES: dict[str, str] = {
    "sending": "sending",
    "failed": "failed",
    "streaming": "streaming",
    "done": "done",
    "sent": "sent",
    "delivered": "delivered",
    "received": "delivered",
    "read": "read",
    "seen": "read",
    "displayed": "read",
}
_MANAGER_SUPPORTED_DIALOG_PREFIXES = {"telegram", "telegram_phone", "whatsapp", "max", "jivo"}


def _normalize_message_status(raw_status: Any) -> str:
    value = str(raw_status or "").strip().lower()
    if not value:
        return "done"
    return _MESSAGE_STATUS_ALIASES.get(value, "done")


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
                    elif event_type == "message_updated":
                        yield {
                            "event": "message_updated",
                            "data": json.dumps(event_data)
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

def _pop_tool_meta(
    tool_matcher: dict[str, list[dict[str, Any]]] | None,
    tool_name: str | None,
) -> dict[str, Any]:
    """Снять метаданные (duration_ms/status) очередного вызова инструмента по имени."""
    if not tool_matcher or not tool_name:
        return {}
    queue = tool_matcher.get(tool_name)
    if not queue:
        return {}
    return queue.pop(0)


def _map_session_message(
    msg_data: dict[str, Any],
    msg_id: UUID,
    created_at: datetime,
    session_id: str | None = None,
    agent_id: UUID | None = None,
    tool_matcher: dict[str, list[dict[str, Any]]] | None = None,
) -> list[MessageRead]:
    """
    Маппинг системного сообщения pydantic-ai в список сообщений для фронтенда.

    Возвращает текстовые сообщения, а также карточки вызова инструментов
    (``tool_call`` / ``tool_result``). Технические инструменты (имя с префиксом
    ``__``) пропускаются. ``tool_matcher`` (если передан) обогащает результаты
    вызовов длительностью и статусом из ``tool_call_logs``.
    """
    from app.utils.message_mapping import (
        infer_role,
        extract_user_info,
        extract_structured_parts,
        extract_text_contents,
    )

    mapped_role = infer_role(msg_data)
    user_info = extract_user_info(msg_data)
    structured = extract_structured_parts(msg_data)
    status_value = _normalize_message_status(msg_data.get("status"))

    # Fallback для сообщений без parts / нестандартного формата: сохраняем прежнее
    # поведение (широкий разбор по известным ключам) как текстовые части.
    if not structured:
        structured = [
            {"kind": "text", "part_kind": None, "content": text}
            for text in extract_text_contents(msg_data)
            if text
        ]

    sender_kind: str | None = None
    sender_label: str | None = None
    ui = user_info or {}
    if mapped_role == "agent":
        sender_kind = "agent"
        sender_label = "Агент"
    elif mapped_role == "user":
        sender_kind = str(ui.get("message_sender_kind") or "contact")
        sender_label = ui.get("sender_display_label")
        if not sender_label:
            sender_label = "Клиент" if sender_kind == "contact" else sender_kind
    elif mapped_role == "manager":
        if ui.get("manager_source") == "wappi_linked_messenger":
            sender_kind = "wappi_operator"
            ch = ui.get("integration_channel_label") or "мессенджер"
            sender_label = f"Оператор ({ch})"
        else:
            sender_kind = "manager"
            sender_label = "Менеджер"
    elif mapped_role == "system":
        sender_kind = "system"
        sender_label = "Система"

    messages: list[MessageRead] = []
    for part in structured:
        kind = part.get("kind")

        if kind == "text":
            content = str(part.get("content") or "")
            if not content:
                continue
            messages.append(
                MessageRead(
                    id=msg_id,
                    session_id=session_id,
                    agent_id=agent_id,
                    role=mapped_role,
                    type="text",
                    content=content,
                    status=status_value,
                    created_at=created_at,
                    user_info=user_info,
                    sender_kind=sender_kind,
                    sender_label=sender_label,
                    part_kind=part.get("part_kind"),
                )
            )
            continue

        tool_name = part.get("tool_name")
        # Технические инструменты не показываем (например, __end_dialog)
        if isinstance(tool_name, str) and tool_name.startswith("__"):
            continue

        if kind == "tool-call":
            messages.append(
                MessageRead(
                    id=msg_id,
                    session_id=session_id,
                    agent_id=agent_id,
                    role="agent",
                    type="tool_call",
                    content="",
                    status=status_value,
                    created_at=created_at,
                    sender_kind="agent",
                    sender_label="Агент",
                    part_kind=part.get("part_kind"),
                    tool_name=tool_name,
                    tool_call_id=part.get("tool_call_id"),
                    args=part.get("args") if isinstance(part.get("args"), dict) else None,
                )
            )
            continue

        if kind == "tool-return":
            meta = _pop_tool_meta(tool_matcher, tool_name if isinstance(tool_name, str) else None)
            messages.append(
                MessageRead(
                    id=msg_id,
                    session_id=session_id,
                    agent_id=agent_id,
                    role="agent",
                    type="tool_result",
                    content="",
                    status=status_value,
                    created_at=created_at,
                    sender_kind="agent",
                    sender_label="Агент",
                    part_kind=part.get("part_kind"),
                    tool_name=tool_name,
                    tool_call_id=part.get("tool_call_id"),
                    args=part.get("args") if isinstance(part.get("args"), dict) else None,
                    result=part.get("result"),
                    duration_ms=meta.get("duration_ms"),
                    tool_status=meta.get("status"),
                )
            )
            continue

    return messages


async def _update_manager_message_delivery_state(
    db: AsyncSession,
    *,
    agent_id: UUID,
    dialog_id: str,
    message_entry: SessionMessage | None,
    status_value: str,
    provider_message_id: str | None = None,
    provider_task_id: str | None = None,
    provider_uuid: str | None = None,
    error_message: str | None = None,
) -> None:
    if message_entry is None:
        return

    payload = message_entry.message if isinstance(message_entry.message, dict) else {}
    payload = {**payload}
    payload["status"] = status_value
    payload["delivery_status_updated_at"] = datetime.utcnow().isoformat()
    if provider_message_id:
        payload["provider_message_id"] = provider_message_id
    if provider_task_id:
        payload["provider_task_id"] = provider_task_id
    if provider_uuid:
        payload["provider_uuid"] = provider_uuid
    if error_message:
        payload["outbound_error"] = error_message
    message_entry.message = payload
    await db.commit()

    await broadcaster.publish(
        agent_id,
        {
            "type": "message_updated",
            "data": {
                "id": str(message_entry.id),
                "session_id": dialog_id,
                "agent_id": str(agent_id),
                "status": status_value,
                "provider_message_id": provider_message_id,
            },
        },
    )

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

    # Мета запусков (токены/стоимость/латентность) и логи вызовов инструментов
    # (длительность/статус) — подгружаем пачкой по run_id этих сообщений.
    run_ids = {db_msg.run_id for db_msg in db_messages if db_msg.run_id}
    run_meta_by_id: dict[UUID, dict[str, Any]] = {}
    tool_matchers_by_run: dict[UUID, dict[str, list[dict[str, Any]]]] = {}
    if run_ids:
        runs = (
            await db.execute(select(Run).where(Run.id.in_(run_ids)))
        ).scalars().all()
        for run_row in runs:
            tokens = run_row.total_tokens
            if tokens is None and (run_row.prompt_tokens is not None or run_row.completion_tokens is not None):
                tokens = (run_row.prompt_tokens or 0) + (run_row.completion_tokens or 0)
            latency_ms: int | None = None
            if run_row.updated_at and run_row.created_at:
                delta = (run_row.updated_at - run_row.created_at).total_seconds()
                if delta > 0:
                    latency_ms = int(delta * 1000)
            run_meta_by_id[run_row.id] = {
                "tokens": tokens or None,
                "cost_rub": float(run_row.cost_rub) if run_row.cost_rub is not None else None,
                "latency_ms": latency_ms,
            }

        tool_logs = (
            await db.execute(
                select(ToolCallLog)
                .where(ToolCallLog.run_id.in_(run_ids))
                .order_by(ToolCallLog.invoked_at.asc())
            )
        ).scalars().all()
        for log_row in tool_logs:
            tool_matchers_by_run.setdefault(log_row.run_id, {}).setdefault(
                log_row.tool_name, []
            ).append({"duration_ms": log_row.duration_ms, "status": log_row.status})

    # Собираем MessageRead, помня для каждого run последнее текстовое сообщение агента,
    # чтобы прикрепить к нему мету запуска.
    mapped_objects: list[MessageRead] = []
    last_agent_text_by_run: dict[UUID, MessageRead] = {}
    for db_msg in db_messages:
        try:
            mapped = _map_session_message(
                db_msg.message,
                db_msg.id,
                db_msg.created_at,
                session_id=dialog_id,
                agent_id=agent_id,
                tool_matcher=tool_matchers_by_run.get(db_msg.run_id) if db_msg.run_id else None,
            )
        except Exception as e:
            logger.error("map_message_error", error=str(e), msg_id=str(db_msg.id))
            continue
        for m in mapped:
            mapped_objects.append(m)
            if db_msg.run_id and m.type == "text" and m.role == "agent":
                last_agent_text_by_run[db_msg.run_id] = m

    # Крепим мету запуска к финальному текстовому ответу агента.
    for run_id, meta in run_meta_by_id.items():
        target = last_agent_text_by_run.get(run_id)
        if target is None:
            continue
        target.tokens = meta["tokens"]
        target.cost_rub = meta["cost_rub"]
        target.latency_ms = meta["latency_ms"]

    all_mapped = [m.model_dump(mode="json") for m in mapped_objects]
    
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
        user_info: dict[str, Any] = {"session_id": dialog_id}
        if dialog_id.startswith("telegram:"):
            user_info["platform"] = "telegram"
            user_info["platform_id"] = dialog_id.split(":", 1)[1]
            user_info["integration_channel_label"] = "Telegram бот"
            user_info["integration_channel_type"] = "telegram"
        elif dialog_id.startswith("telegram_phone:"):
            user_info["platform"] = "telegram_phone"
            user_info["platform_id"] = dialog_id.split(":", 1)[1]
            user_info["integration_channel_label"] = "Telegram номер"
            user_info["integration_channel_type"] = "telegram_phone"
        elif dialog_id.startswith("max:"):
            user_info["platform"] = "max"
            user_info["platform_id"] = dialog_id.split(":", 1)[1]
            user_info["integration_channel_label"] = "MAX"
            user_info["integration_channel_type"] = "max"
        elif dialog_id.startswith("whatsapp:"):
            user_info["platform"] = "whatsapp"
            user_info["platform_id"] = dialog_id.split(":", 1)[1]
            user_info["integration_channel_label"] = "WhatsApp"
            user_info["integration_channel_type"] = "whatsapp"

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
                fallback_tokens = run.total_tokens
                if fallback_tokens is None and (run.prompt_tokens is not None or run.completion_tokens is not None):
                    fallback_tokens = (run.prompt_tokens or 0) + (run.completion_tokens or 0)
                fallback_latency_ms: int | None = None
                if run.updated_at and run.created_at:
                    fallback_delta = (run.updated_at - run.created_at).total_seconds()
                    if fallback_delta > 0:
                        fallback_latency_ms = int(fallback_delta * 1000)
                fallback_messages.append({
                    "id": f"{run.id}:agent",
                    "session_id": dialog_id,
                    "agent_id": str(agent_id),
                    "role": "agent",
                    "type": "text",
                    "content": run.output_message,
                    "status": "done",
                    "created_at": (run.updated_at or run.created_at).isoformat(),
                    "user_info": user_info,
                    "tokens": fallback_tokens or None,
                    "cost_rub": float(run.cost_rub) if run.cost_rub is not None else None,
                    "latency_ms": fallback_latency_ms,
                })

        logger.info("list_messages_fallback_runs", count=len(fallback_messages))
        all_mapped = fallback_messages

    logger.info("list_messages_mapped", count=len(all_mapped))
    return {"messages": all_mapped[-limit:]}

@router.delete("/{dialog_id}/history")
async def clear_dialog_history(
    agent_id: UUID,
    dialog_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("dialogs:write")),
) -> dict[str, Any]:
    """
    Очистить историю сообщений диалога (удалить все session_messages).
    """
    agent = await get_agent_or_404(agent_id, db, user)

    stmt = (
        delete(SessionMessage)
        .where(
            SessionMessage.session_id == dialog_id,
            SessionMessage.tenant_id == agent.tenant_id,
        )
    )
    result = await db.execute(stmt)
    await db.commit()

    deleted_count = result.rowcount
    logger.info(
        "dialog_history_cleared",
        agent_id=str(agent_id),
        dialog_id=dialog_id,
        deleted_count=deleted_count,
    )

    return {"ok": True, "deleted_count": deleted_count}


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
    2. Отправляет сообщение пользователю через канал диалога.
    3. Обновляет статус доставки и last_manager_message_at для автопаузы агента.
    """
    agent = await get_agent_or_404(agent_id, db, user)
    normalized_content = payload.content.strip()
    if not normalized_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content must not be empty",
        )

    dialog_prefix = dialog_id.split(":", 1)[0].strip().lower() if ":" in dialog_id else ""
    if dialog_prefix not in _MANAGER_SUPPORTED_DIALOG_PREFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Manager messages are not supported for dialog '{dialog_id}'",
        )

    # --- Создать Run для менеджерского сообщения ---
    from uuid import uuid4

    trace_id = str(uuid4())
    run = Run(
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        session_id=dialog_id,
        status="succeeded",
        input_message=normalized_content,
        trace_id=trace_id,
    )
    db.add(run)
    await db.flush()

    # --- Сохранить сообщение менеджера (пока в статусе sending) ---
    manager_msg = build_manager_message(normalized_content)
    manager_msg.update(
        {
            "status": "sending",
            "outbound_channel_type": dialog_prefix,
            "manager_source": "ui",
        }
    )
    manager_user_info = {
        "platform": "manager",
        "session_id": dialog_id,
        "manager_user_id": str(user.user_id),
        "manager_source": "ui",
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

    manager_entry_stmt = (
        select(SessionMessage)
        .where(
            SessionMessage.run_id == run.id,
            SessionMessage.session_id == dialog_id,
            SessionMessage.tenant_id == user.tenant_id,
        )
        .order_by(SessionMessage.message_index.desc())
        .limit(1)
    )
    manager_entry = (await db.execute(manager_entry_stmt)).scalar_one_or_none()

    run.updated_at = datetime.utcnow()
    await db.commit()

    try:
        dispatch_result = await dispatch_manager_message(
            db,
            agent_id=agent_id,
            dialog_id=dialog_id,
            content=normalized_content,
            manager_user_id=user.user_id,
        )
    except ManagerDispatchError as exc:
        await _update_manager_message_delivery_state(
            db,
            agent_id=agent_id,
            dialog_id=dialog_id,
            message_entry=manager_entry,
            status_value="failed",
            error_message=str(exc),
        )
        logger.warning(
            "manager_message_dispatch_failed",
            agent_id=str(agent_id),
            dialog_id=dialog_id,
            channel_type=dialog_prefix,
            error=str(exc),
        )
        raise HTTPException(status_code=exc.http_status_code, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        await _update_manager_message_delivery_state(
            db,
            agent_id=agent_id,
            dialog_id=dialog_id,
            message_entry=manager_entry,
            status_value="failed",
            error_message=str(exc),
        )
        logger.exception(
            "manager_message_dispatch_unexpected_error",
            agent_id=str(agent_id),
            dialog_id=dialog_id,
            channel_type=dialog_prefix,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось отправить сообщение во внешний канал",
        ) from exc

    await _update_manager_message_delivery_state(
        db,
        agent_id=agent_id,
        dialog_id=dialog_id,
        message_entry=manager_entry,
        status_value="sent",
        provider_message_id=dispatch_result.provider_message_id,
        provider_task_id=dispatch_result.provider_task_id,
        provider_uuid=dispatch_result.provider_uuid,
    )

    # Пауза обновляется только при успешной отправке операторского сообщения.
    await update_last_manager_message(
        db,
        agent_id=agent_id,
        tenant_id=user.tenant_id,
        session_id=dialog_id,
    )

    # Фаза manager_message: даёт правилам сработать после вмешательства оператора.
    # Пример правила: «после ответа менеджера пометить сессию тегом hot_lead» или
    # «после ответа менеджера отменить запланированный follow-up».
    try:
        await run_rules_for_phase(
            db,
            tenant_id=user.tenant_id,
            agent_id=agent_id,
            session_id=dialog_id,
            trace_id=str(_uuid4_for_trace()),
            phase="manager_message",
            message=str(normalized_content or ""),
            user=user,
            run_id=None,
            context={
                "user_info": {},
                "agent_timezone": "UTC",
                "manager_message": str(normalized_content or ""),
                "channel_type": dispatch_result.channel_type,
            },
        )
    except Exception as _mm_exc:  # noqa: BLE001
        logger.warning(
            "manager_message_rules_dispatch_failed",
            agent_id=str(agent_id),
            dialog_id=dialog_id,
            error=str(_mm_exc),
        )

    logger.info(
        "manager_message_sent",
        agent_id=str(agent_id),
        dialog_id=dialog_id,
        channel_type=dispatch_result.channel_type,
        provider_message_id=dispatch_result.provider_message_id,
        provider_task_id=dispatch_result.provider_task_id,
    )

    return {
        "ok": True,
        "message_id": str(manager_entry.id) if manager_entry is not None else str(run.id),
        "dialog_id": dialog_id,
        "delivery_status": "sent",
        "channel_type": dispatch_result.channel_type,
        "provider_message_id": dispatch_result.provider_message_id,
        "provider_task_id": dispatch_result.provider_task_id,
        "provider_uuid": dispatch_result.provider_uuid,
    }

