from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrainingSessionCreate(BaseModel):
    """Тело запроса для создания тренировочной сессии."""

    meta_model: str | None = Field(
        default=None,
        description="Модель для мета-агента (например openai:gpt-4.1). Если не указана — берётся из настроек платформы.",
    )


class TrainingFeedbackCreate(BaseModel):
    """Тело запроса для добавления коррекции/фидбека."""

    feedback_type: Literal["correction", "positive", "negative", "instruction"] = Field(
        ..., description="Тип фидбека",
    )
    run_id: UUID | None = Field(
        default=None, description="ID рана, к которому относится фидбек",
    )
    agent_response: str | None = Field(
        default=None, description="Ответ агента, который оценивается",
    )
    correction_text: str = Field(
        ..., description="Текст коррекции / инструкции",
    )


class TrainingFeedbackRead(BaseModel):
    """Ответ при чтении фидбека."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    training_session_id: UUID
    run_id: UUID | None = None
    feedback_type: str
    user_message: str | None = None
    agent_response: str | None = None
    correction_text: str
    order_index: int
    created_at: datetime


class GeneratePromptRequest(BaseModel):
    """Опциональное тело запроса для генерации промпта."""

    meta_model: str | None = Field(
        default=None,
        description="Переопределить модель мета-агента для этой генерации. Если не указана — используется модель из сессии.",
    )


class GeneratedPromptPreview(BaseModel):
    """Предпросмотр сгенерированного промпта перед применением."""

    current_prompt: str
    generated_prompt: str
    reasoning: str
    change_summary: str
    feedback_used: int
    meta_model: str = Field(description="Модель, использованная для генерации промпта (мета-агент)")
    agent_model: str = Field(description="Модель агента, которая отвечает клиентам")


class TrainingSessionRead(BaseModel):
    """Полная информация о тренировочной сессии."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    tenant_id: UUID
    created_by: UUID
    status: str
    base_prompt_version: int
    generated_prompt: str | None = None
    generated_prompt_reasoning: str | None = None
    generated_version_id: UUID | None = None
    feedback_count: int
    meta_model: str = Field(description="Модель мета-агента для генерации промпта")
    agent_model: str | None = Field(default=None, description="Модель агента, которая отвечает клиентам")
    created_at: datetime
    updated_at: datetime | None = None
    feedbacks: list[TrainingFeedbackRead] = Field(default_factory=list)


class TrainingSessionListItem(BaseModel):
    """Краткая запись для списка сессий (без generated_prompt)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    status: str
    base_prompt_version: int
    feedback_count: int
    meta_model: str
    generated_version_id: UUID | None = None
    created_by: UUID
    created_at: datetime


class TrainingSessionListResponse(BaseModel):
    """Ответ списка сессий с курсорной пагинацией."""

    items: list[TrainingSessionListItem]
    next_cursor: str | None = Field(
        default=None,
        description="ID последнего элемента для следующей порции. null = больше данных нет.",
    )
