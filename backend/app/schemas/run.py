from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RunCreate(BaseModel):
    """Схема для создания нового запуска агента."""
    
    agent_id: UUID = Field(..., description="UUID агента для запуска")
    session_id: str | None = Field(default=None, max_length=200, description="ID сессии диалога (для истории сообщений)")
    input_message: str = Field(..., min_length=1, description="Входное сообщение пользователя")


class RunRead(BaseModel):
    """
    Схема ответа для запуска агента.
    
    Содержит полную информацию о выполненном запуске:
    - Статус выполнения и сообщения
    - Использование токенов LLM
    - Список вызванных инструментов
    - Полная история сообщений
    """
    model_config = ConfigDict(from_attributes=True)

    # Идентификаторы
    id: UUID = Field(..., description="UUID запуска")
    tenant_id: UUID = Field(..., description="UUID арендатора")
    agent_id: UUID = Field(..., description="UUID агента")
    session_id: str = Field(..., description="ID сессии диалога (для группировки сообщений)")
    trace_id: str = Field(..., description="ID для трассировки запроса")

    # Статус и сообщения
    status: Literal["queued", "running", "succeeded", "failed"] = Field(..., description="Статус выполнения")
    input_message: str = Field(..., description="Входное сообщение пользователя")
    output_message: str | None = Field(None, description="Ответ агента (заполняется при status='succeeded')")
    error_message: str | None = Field(None, description="Сообщение об ошибке (заполняется при status='failed')")

    # Метаданные
    messages: list[dict[str, Any]] | None = Field(None, description="Полная история сообщений от pydantic-ai (JSONB)")

    # Использование токенов LLM
    prompt_tokens: int | None = Field(None, description="Количество токенов во входном промпте")
    completion_tokens: int | None = Field(None, description="Количество токенов в ответе")
    total_tokens: int | None = Field(None, description="Общее количество токенов (prompt + completion)")
    cost_currency: str = Field("USD", description="Базовая валюта стоимости")
    cost_usd: Decimal | None = Field(None, description="Расчётная стоимость в USD по таблице тарифов")
    cost_rub: Decimal | None = Field(None, description="Расчётная стоимость в RUB по таблице тарифов")
    cost_usd_logfire: Decimal | None = Field(None, description="Стоимость в USD по данным Logfire")

    # Вызванные инструменты
    tools_called: list[dict[str, Any]] | None = Field(
        None,
        description="Список инструментов, вызванных агентом. Формат: [{'name': str, 'tool_call_id': str | None, 'args': dict}]"
    )
    orchestration_meta: dict[str, Any] | None = Field(
        None,
        description="Служебные метаданные оркестрации (например, source direct_question_tool_call).",
    )

    # Временные метки
    created_at: datetime = Field(..., description="Время создания запуска (ISO 8601)")
    updated_at: datetime | None = Field(None, description="Время последнего обновления (ISO 8601)")

    @field_validator("tools_called", mode="before")
    @classmethod
    def _filter_technical_tools(cls, value: Any) -> list[dict[str, Any]] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            return []

        public_tools: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and name.startswith("__"):
                continue
            public_tools.append(item)
        return public_tools
