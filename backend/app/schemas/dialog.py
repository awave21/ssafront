from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


DIALOG_STATUSES = ("active", "paused", "disabled")


class DialogRead(BaseModel):
    """Схема для чтения диалога (сессии)."""
    id: str = Field(..., description="ID сессии (session_id)")
    agent_id: UUID = Field(..., description="UUID агента")
    title: str = Field(..., description="Заголовок диалога")
    last_message_preview: str | None = Field(None, description="Превью последнего сообщения")
    last_message_at: datetime = Field(..., description="Время последнего сообщения")
    unread_count: int = Field(0, description="Количество непрочитанных (заглушка)")
    is_pinned: bool = Field(False, description="Закреплен ли чат (заглушка)")
    status: str = Field("active", description="Статус чата: active / paused / disabled")
    user_info: dict[str, Any] | None = Field(None, description="Информация о пользователе (Telegram и др.)")


class DialogStatusUpdate(BaseModel):
    """Схема для обновления статуса диалога."""
    status: Literal["active", "paused", "disabled"] = Field(
        ..., description="Новый статус: active, paused или disabled"
    )


class MessageRead(BaseModel):
    """Схема для чтения сообщения."""
    id: UUID | str = Field(..., description="ID сообщения")
    session_id: str | None = Field(None, description="ID сессии")
    agent_id: UUID | str | None = Field(None, description="ID агента")
    role: Literal["user", "agent", "system", "manager"] = Field(..., description="Роль отправителя")
    type: Literal["text", "image", "voice", "tool_call", "tool_result"] = Field("text", description="Тип контента")
    content: str = Field("", description="Текст сообщения")
    status: Literal["sent", "streaming", "done"] = Field("done", description="Статус доставки/генерации")
    created_at: datetime = Field(..., description="Время создания")
    # Дополнительная информация о пользователе (например, из Telegram)
    user_info: dict[str, Any] | None = Field(None, description="Информация об отправителе")
    part_kind: str | None = Field(None, description="Тип части pydantic-ai")
    tool_name: str | None = Field(None, description="Название инструмента")
    tool_call_id: str | None = Field(None, description="ID вызова инструмента")
    args: dict[str, Any] | None = Field(None, description="Аргументы вызова инструмента")
    result: Any | None = Field(None, description="Результат инструмента")


class MessageCreate(BaseModel):
    """Схема для создания сообщения."""
    content: str = Field(..., min_length=1, description="Текст сообщения")
    type: Literal["text", "image", "voice"] = Field("text", description="Тип сообщения")


class ManagerMessageCreate(BaseModel):
    """Схема для отправки сообщения менеджером."""
    content: str = Field(..., min_length=1, description="Текст сообщения менеджера")


class StreamRequest(BaseModel):
    """Запрос на стриминг ответа."""
    user_message_id: str | None = Field(None, description="ID отправленного сообщения (опционально)")
