"""
WebSocket роутер для real-time коммуникации с агентами.

Заменяет SSE эндпоинты на двунаправленный WebSocket канал.
"""
from __future__ import annotations

import json
import os
import time
import asyncio
import structlog
from uuid import UUID, uuid4
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthError, decode_token
from app.db.models.agent import Agent
from app.db.models.run import Run
from app.db.session import async_session_factory
from app.schemas.auth import AuthContext
from app.utils.broadcast import broadcaster

logger = structlog.get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """Менеджер WebSocket соединений."""

    def __init__(self):
        # {agent_id: {websocket, ...}}
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, agent_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            if agent_id not in self._connections:
                self._connections[agent_id] = set()
            self._connections[agent_id].add(websocket)
        logger.info(
            "ws_connected",
            agent_id=agent_id,
            total=len(self._connections[agent_id]),
        )

    async def disconnect(self, websocket: WebSocket, agent_id: str) -> None:
        async with self._lock:
            if agent_id in self._connections:
                self._connections[agent_id].discard(websocket)
                if not self._connections[agent_id]:
                    del self._connections[agent_id]
        logger.info("ws_disconnected", agent_id=agent_id)

    async def send_json(self, websocket: WebSocket, data: dict[str, Any]) -> bool:
        """Отправить JSON сообщение. Возвращает False если соединение закрыто."""
        try:
            await websocket.send_json(data)
            return True
        except Exception as e:
            logger.warning("ws_send_failed", error=str(e))
            return False

    def get_connection_count(self, agent_id: str) -> int:
        return len(self._connections.get(agent_id, set()))


# Глобальный менеджер соединений
manager = ConnectionManager()


async def validate_ws_token(token: str) -> AuthContext:
    """Валидация JWT токена для WebSocket соединения."""
    try:
        return decode_token(token)
    except AuthError as e:
        raise ValueError(f"Invalid token: {e}") from e


async def verify_agent_access(
    db: AsyncSession,
    agent_id: UUID,
    tenant_id: UUID,
) -> Agent | None:
    """Проверка доступа к агенту."""
    stmt = select(Agent).where(
        Agent.id == agent_id,
        Agent.tenant_id == tenant_id,
        Agent.is_deleted.is_(False),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@router.websocket("/agents/{agent_id}/ws")
async def agent_websocket(
    websocket: WebSocket,
    agent_id: UUID,
    token: str = Query(..., description="JWT токен авторизации"),
):
    """
    WebSocket канал для получения событий агента в реальном времени.

    Подключение: ws://host/api/v1/agents/{agent_id}/ws?token=JWT_TOKEN

    Типы входящих событий (от клиента):
    - send_message: отправить сообщение в диалог
    - run_agent: запустить агента на сообщение
    - join_dialog: подписаться на конкретный диалог
    - pong: ответ на ping

    Типы исходящих событий (от сервера):
    - message_created: новое сообщение
    - dialog_updated: обновление диалога
    - run_start: начало выполнения агента
    - run_result: результат выполнения
    - run_error: ошибка выполнения
    - ping: keep-alive
    - error: ошибка обработки
    """
    # 1. Валидация токена
    try:
        user = await validate_ws_token(token)
    except ValueError as e:
        logger.warning("ws_auth_failed", agent_id=str(agent_id), error=str(e))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    # 2. Проверка доступа к агенту
    async with async_session_factory() as db:
        agent = await verify_agent_access(db, agent_id, user.tenant_id)
        if not agent:
            logger.warning("ws_agent_not_found", agent_id=str(agent_id), tenant_id=str(user.tenant_id))
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Agent not found")
            return
    # region agent log
    try:
        os.makedirs("/opt/app-agent/myapp/backend/.cursor", exist_ok=True)
        with open("/opt/app-agent/myapp/backend/.cursor/debug-e26c68.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "e26c68",
                "runId": "audit-1",
                "hypothesisId": "H1",
                "location": "app/api/routers/ws.py:agent_websocket",
                "message": "ws_connected_auth",
                "data": {
                    "agent_id": str(agent_id),
                    "tenant_id": str(user.tenant_id),
                    "user_id": str(user.user_id),
                    "scopes": list(user.scopes) if user.scopes else [],
                },
                "timestamp": int(time.time() * 1000),
            }) + "\n")
    except Exception:
        pass
    # endregion agent log

    agent_id_str = str(agent_id)
    await manager.connect(websocket, agent_id_str)

    # 3. Подписываемся на broadcast шину
    queue = await broadcaster.subscribe(agent_id)

    try:
        # Создаем задачи для параллельной работы
        broadcast_task = asyncio.create_task(
            _listen_broadcast(websocket, queue, agent_id_str)
        )
        client_task = asyncio.create_task(
            _listen_client(websocket, agent_id, user)
        )
        ping_task = asyncio.create_task(
            _ping_loop(websocket)
        )

        # Ожидаем завершения любой из задач
        done, pending = await asyncio.wait(
            [broadcast_task, client_task, ping_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Отменяем остальные задачи
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", agent_id=agent_id_str)
    except Exception as e:
        logger.error("ws_error", agent_id=agent_id_str, error=str(e))
    finally:
        await broadcaster.unsubscribe(agent_id, queue)
        await manager.disconnect(websocket, agent_id_str)


def _map_pydantic_message_to_ws_format(
    msg_data: dict[str, Any],
    msg_id: str,
    session_id: str,
    agent_id: str,
    created_at: str,
) -> list[dict[str, Any]]:
    """
    Маппинг сообщения pydantic-ai в формат WSMessageData.
    Возвращает список сообщений (может быть несколько частей).
    """
    from app.utils.message_mapping import infer_role, extract_structured_parts, extract_user_info

    mapped_role = infer_role(msg_data)
    user_info = extract_user_info(msg_data)
    structured_parts = extract_structured_parts(msg_data)

    mapped_messages: list[dict[str, Any]] = []
    for part in structured_parts:
        kind = part.get("kind")
        mapped_messages.append(
            {
                "id": msg_id,
                "session_id": session_id,
                "agent_id": agent_id,
                "role": mapped_role,
                "content": str(part.get("content", "")) if kind == "text" else "",
                "created_at": created_at,
                "user_info": user_info,
                "part_kind": part.get("part_kind"),
                "tool_name": part.get("tool_name"),
                "tool_call_id": part.get("tool_call_id"),
                "args": part.get("args") if isinstance(part.get("args"), dict) else None,
                "result": part.get("result"),
            }
        )

    return mapped_messages


async def _listen_broadcast(
    websocket: WebSocket,
    queue: asyncio.Queue,
    agent_id: str,
) -> None:
    """Слушаем broadcast шину и отправляем события клиенту."""
    while True:
        try:
            event = await queue.get()
            event_type = event.get("type")

            # Маппим message_created события в правильный формат
            if event_type == "message_created":
                event_data = event.get("data", {})
                msg_data = event_data.get("message", {})
                msg_id = event_data.get("id", str(uuid4()))
                session_id = event_data.get("session_id", "")
                evt_agent_id = event_data.get("agent_id", agent_id)
                created_at = event_data.get("created_at", datetime.utcnow().isoformat())

                mapped_messages = _map_pydantic_message_to_ws_format(
                    msg_data,
                    msg_id,
                    session_id,
                    evt_agent_id,
                    created_at,
                )

                for mapped_msg in mapped_messages:
                    success = await manager.send_json(websocket, {
                        "type": "message_created",
                        "data": mapped_msg,
                    })
                    if not success:
                        return
            else:
                # Остальные события отправляем как есть
                success = await manager.send_json(websocket, event)
                if not success:
                    break
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("ws_broadcast_error", agent_id=agent_id, error=str(e))
            break


async def _listen_client(
    websocket: WebSocket,
    agent_id: UUID,
    user: AuthContext,
) -> None:
    """Слушаем сообщения от клиента и обрабатываем их."""
    while True:
        try:
            data = await websocket.receive_json()
            await _handle_client_message(websocket, agent_id, data, user)
        except WebSocketDisconnect:
            raise
        except asyncio.CancelledError:
            break
        except json.JSONDecodeError as e:
            await manager.send_json(websocket, {
                "type": "error",
                "data": {"message": f"Invalid JSON: {e}"}
            })
        except Exception as e:
            logger.error("ws_client_handler_error", error=str(e))
            await manager.send_json(websocket, {
                "type": "error",
                "data": {"message": str(e)}
            })


async def _ping_loop(websocket: WebSocket) -> None:
    """Отправляем ping каждые 20 секунд для поддержания соединения."""
    while True:
        try:
            await asyncio.sleep(20)
            success = await manager.send_json(websocket, {
                "type": "ping",
                "data": {"timestamp": datetime.utcnow().isoformat()}
            })
            if not success:
                break
        except asyncio.CancelledError:
            break
        except Exception:
            break


async def _handle_client_message(
    websocket: WebSocket,
    agent_id: UUID,
    data: dict[str, Any],
    user: AuthContext,
) -> None:
    """Обработка входящих сообщений от клиента."""
    msg_type = data.get("type")

    if msg_type == "pong":
        # Ответ на ping — игнорируем
        return

    elif msg_type == "send_message":
        # Отправка сообщения в диалог (через агента)
        dialog_id = data.get("dialog_id")
        content = data.get("content")

        if not dialog_id or not content:
            await manager.send_json(websocket, {
                "type": "error",
                "data": {"message": "dialog_id and content are required"}
            })
            return

        await _run_agent_response(websocket, agent_id, dialog_id, content, user)

    elif msg_type == "run_agent":
        # Запуск агента на сообщение (аналог send_message)
        dialog_id = data.get("dialog_id")
        content = data.get("content")

        if not dialog_id or not content:
            await manager.send_json(websocket, {
                "type": "error",
                "data": {"message": "dialog_id and content are required"}
            })
            return

        await _run_agent_response(websocket, agent_id, dialog_id, content, user)

    elif msg_type == "join_dialog":
        # Подписка на конкретный диалог (для фильтрации событий на клиенте)
        dialog_id = data.get("dialog_id")
        await manager.send_json(websocket, {
            "type": "dialog_joined",
            "data": {"dialog_id": dialog_id}
        })

    elif msg_type == "leave_dialog":
        # Отписка от диалога
        dialog_id = data.get("dialog_id")
        await manager.send_json(websocket, {
            "type": "dialog_left",
            "data": {"dialog_id": dialog_id}
        })

    elif msg_type == "get_status":
        # Получение статуса соединения
        await manager.send_json(websocket, {
            "type": "status",
            "data": {
                "connected": True,
                "agent_id": str(agent_id),
                "connections_count": manager.get_connection_count(str(agent_id)),
            }
        })

    else:
        await manager.send_json(websocket, {
            "type": "error",
            "data": {"message": f"Unknown message type: {msg_type}"}
        })


async def _run_agent_response(
    websocket: WebSocket,
    agent_id: UUID,
    dialog_id: str,
    content: str,
    user: AuthContext,
) -> None:
    """Запуск агента и отправка ответа через WebSocket."""
    from app.services.logfire_cost_reconcile import schedule_logfire_cost_reconcile
    from app.services.runtime import logger as runtime_logger
    from app.services.run_service import (
        execute_agent_run,
        get_session_history,
        load_agent_and_tools,
    )

    trace_id = str(uuid4())

    # Создаем run
    async with async_session_factory() as session:
        try:
            agent, tools, bindings = await load_agent_and_tools(
                session, agent_id, user.tenant_id
            )
            message_history = await get_session_history(
                session, dialog_id, user.tenant_id, agent.id, limit=agent.max_history_messages
            )

            run = Run(
                tenant_id=user.tenant_id,
                agent_id=agent_id,
                session_id=dialog_id,
                status="running",
                input_message=content,
                trace_id=trace_id,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)

        except Exception as e:
            await manager.send_json(websocket, {
                "type": "run_error",
                "data": {"error": f"Failed to create run: {e}"}
            })
            return

    # Отправляем событие начала
    await manager.send_json(websocket, {
        "type": "run_start",
        "data": {
            "run_id": str(run.id),
            "trace_id": trace_id,
            "dialog_id": dialog_id,
        }
    })

    # Выполняем агента
    async with async_session_factory() as session:
        try:
            agent, tools, bindings = await load_agent_and_tools(
                session, agent_id, user.tenant_id
            )

            result = await execute_agent_run(
                session,
                agent=agent,
                tools=tools,
                bindings=bindings,
                run=run,
                input_message=content,
                trace_id=trace_id,
                user=user,
                session_id=dialog_id,
                message_history=message_history,
            )

            await session.merge(run)
            await session.commit()
            schedule_logfire_cost_reconcile(run_id=run.id, trace_id=trace_id)

            await manager.send_json(websocket, {
                "type": "run_result",
                "data": {
                    "run_id": str(run.id),
                    "output": result.output,
                    "dialog_id": dialog_id,
                    "tokens": {
                        "prompt": result.prompt_tokens,
                        "completion": result.completion_tokens,
                        "total": result.total_tokens,
                    },
                    "cost": {
                        "usd": float(run.cost_usd) if run.cost_usd is not None else None,
                        "rub": float(run.cost_rub) if run.cost_rub is not None else None,
                        "usd_logfire": float(run.cost_usd_logfire) if run.cost_usd_logfire is not None else None,
                    },
                    "tools_called": result.tools_called,
                    "orchestration_meta": result.orchestration_meta,
                }
            })

        except Exception as e:
            runtime_logger.exception("ws_run_failed", trace_id=trace_id, error=str(e))
            run.status = "failed"
            run.error_message = str(e)
            run.logfire_reconcile_status = "skipped"
            run.logfire_reconcile_error = "run_failed"

            await session.merge(run)
            await session.commit()

            await manager.send_json(websocket, {
                "type": "run_error",
                "data": {
                    "run_id": str(run.id),
                    "error": str(e),
                    "dialog_id": dialog_id,
                }
            })
