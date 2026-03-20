"""
Схемы для WebSocket событий.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# === Входящие события (от клиента) ===

class WSClientMessage(BaseModel):
    """Базовое сообщение от клиента."""
    type: str = Field(..., description="Тип события")


class WSSendMessage(WSClientMessage):
    """Отправка сообщения в диалог."""
    type: Literal["send_message"] = "send_message"
    dialog_id: str = Field(..., description="ID диалога (session_id)")
    content: str = Field(..., min_length=1, description="Текст сообщения")


class WSRunAgent(WSClientMessage):
    """Запуск агента на сообщение."""
    type: Literal["run_agent"] = "run_agent"
    dialog_id: str = Field(..., description="ID диалога")
    content: str = Field(..., min_length=1, description="Текст сообщения")


class WSJoinDialog(WSClientMessage):
    """Подписка на диалог."""
    type: Literal["join_dialog"] = "join_dialog"
    dialog_id: str = Field(..., description="ID диалога")


class WSLeaveDialog(WSClientMessage):
    """Отписка от диалога."""
    type: Literal["leave_dialog"] = "leave_dialog"
    dialog_id: str = Field(..., description="ID диалога")


class WSPong(WSClientMessage):
    """Ответ на ping."""
    type: Literal["pong"] = "pong"


class WSGetStatus(WSClientMessage):
    """Запрос статуса."""
    type: Literal["get_status"] = "get_status"


# === Исходящие события (от сервера) ===

class WSServerMessage(BaseModel):
    """Базовое сообщение от сервера."""
    type: str = Field(..., description="Тип события")
    data: dict[str, Any] = Field(default_factory=dict, description="Данные события")


class WSPing(WSServerMessage):
    """Keep-alive ping."""
    type: Literal["ping"] = "ping"
    data: dict[str, Any] = Field(default_factory=lambda: {"timestamp": datetime.utcnow().isoformat()})


class WSError(WSServerMessage):
    """Ошибка обработки."""
    type: Literal["error"] = "error"


class WSRunStart(BaseModel):
    """Начало выполнения агента."""
    type: Literal["run_start"] = "run_start"
    data: "WSRunStartData"


class WSRunStartData(BaseModel):
    run_id: str = Field(..., description="ID запуска")
    trace_id: str = Field(..., description="ID трассировки")
    dialog_id: str = Field(..., description="ID диалога")


class WSRunResult(BaseModel):
    """Результат выполнения агента."""
    type: Literal["run_result"] = "run_result"
    data: "WSRunResultData"


class WSRunResultData(BaseModel):
    run_id: str = Field(..., description="ID запуска")
    output: str = Field(..., description="Ответ агента")
    dialog_id: str = Field(..., description="ID диалога")
    tokens: "WSTokenUsage | None" = Field(None, description="Использование токенов")
    cost: "WSCostUsage | None" = Field(None, description="Стоимость запуска")
    tools_called: list[dict[str, Any]] | None = Field(
        None,
        description="Вызванные инструменты. Формат: [{'name': str, 'tool_call_id': str | None, 'args': dict}]",
    )
    orchestration_meta: dict[str, Any] | None = Field(
        None,
        description="Служебные метаданные оркестрации (например, source direct_question_tool_call).",
    )


class WSTokenUsage(BaseModel):
    prompt: int | None = None
    completion: int | None = None
    total: int | None = None


class WSCostUsage(BaseModel):
    usd: float | None = None
    rub: float | None = None
    usd_logfire: float | None = None


class WSRunError(BaseModel):
    """Ошибка выполнения агента."""
    type: Literal["run_error"] = "run_error"
    data: "WSRunErrorData"


class WSRunErrorData(BaseModel):
    run_id: str | None = Field(None, description="ID запуска")
    error: str = Field(..., description="Текст ошибки")
    dialog_id: str | None = Field(None, description="ID диалога")


class WSMessageCreated(BaseModel):
    """Новое сообщение создано."""
    type: Literal["message_created"] = "message_created"
    data: "WSMessageData"


class WSMessageData(BaseModel):
    id: str = Field(..., description="ID сообщения")
    session_id: str = Field(..., description="ID сессии")
    agent_id: str = Field(..., description="ID агента")
    role: Literal["user", "agent", "system", "manager"] = Field(..., description="Роль")
    content: str = Field("", description="Текст сообщения")
    created_at: str = Field(..., description="Время создания ISO")
    user_info: dict[str, Any] | None = Field(None, description="Информация о пользователе")
    part_kind: str | None = Field(None, description="Тип части pydantic-ai (например tool-call)")
    tool_name: str | None = Field(None, description="Название вызванного инструмента")
    tool_call_id: str | None = Field(None, description="ID вызова инструмента для корреляции")
    args: dict[str, Any] | None = Field(None, description="Аргументы вызова инструмента")
    result: Any | None = Field(None, description="Результат выполнения инструмента")


class WSToolCall(BaseModel):
    """Событие вызова инструмента."""
    type: Literal["tool_call"] = "tool_call"
    data: "WSToolEventData"


class WSToolResult(BaseModel):
    """Событие результата инструмента."""
    type: Literal["tool_result"] = "tool_result"
    data: "WSToolEventData"


class WSToolEventData(BaseModel):
    session_id: str = Field(..., description="ID сессии")
    agent_id: str = Field(..., description="ID агента")
    created_at: str = Field(..., description="Время создания ISO")
    tool_name: str | None = Field(None, description="Название инструмента")
    tool_call_id: str | None = Field(None, description="ID вызова инструмента")
    args: dict[str, Any] | None = Field(None, description="Аргументы вызова")
    result: Any | None = Field(None, description="Результат выполнения")
    message_id: str | None = Field(None, description="ID исходного message_created")


class WSDialogUpdated(BaseModel):
    """Диалог обновлен."""
    type: Literal["dialog_updated"] = "dialog_updated"
    data: "WSDialogData"


class WSDialogData(BaseModel):
    id: str = Field(..., description="ID диалога (session_id)")
    agent_id: str = Field(..., description="ID агента")
    title: str = Field(..., description="Заголовок")
    last_message_preview: str | None = Field(None, description="Превью последнего сообщения")
    last_message_at: str = Field(..., description="Время последнего сообщения ISO")
    is_new: bool = Field(False, description="Новый ли диалог")


class WSDialogJoined(BaseModel):
    """Подтверждение подписки на диалог."""
    type: Literal["dialog_joined"] = "dialog_joined"
    data: dict[str, str]


class WSDialogLeft(BaseModel):
    """Подтверждение отписки от диалога."""
    type: Literal["dialog_left"] = "dialog_left"
    data: dict[str, str]


class WSStatus(BaseModel):
    """Статус соединения."""
    type: Literal["status"] = "status"
    data: "WSStatusData"


class WSStatusData(BaseModel):
    connected: bool = True
    agent_id: str
    connections_count: int


# Update forward refs
WSRunStart.model_rebuild()
WSRunResult.model_rebuild()
WSRunError.model_rebuild()
WSMessageCreated.model_rebuild()
WSToolCall.model_rebuild()
WSToolResult.model_rebuild()
WSDialogUpdated.model_rebuild()
WSStatus.model_rebuild()
