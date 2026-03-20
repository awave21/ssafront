from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SystemPromptVersionCreate(BaseModel):
    """Тело запроса для создания новой версии системного промпта."""

    system_prompt: str = Field(..., description="Текст системного промпта")
    change_summary: str | None = Field(
        default=None,
        max_length=500,
        description="Краткое описание изменения",
    )
    activate: bool = Field(
        default=True,
        description="Активировать эту версию сразу (обновить агента)",
    )


class SystemPromptVersionRead(BaseModel):
    """Ответ при чтении версии системного промпта."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    tenant_id: UUID
    version_number: int
    system_prompt: str
    change_summary: str | None = None
    triggered_by: str
    is_active: bool
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class SystemPromptVersionListItem(BaseModel):
    """Краткая запись для списка версий (без полного текста промпта)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    version_number: int
    change_summary: str | None = None
    triggered_by: str
    is_active: bool
    created_by: UUID | None = None
    created_at: datetime
    prompt_length: int = Field(
        default=0,
        description="Длина текста промпта в символах",
    )


class SystemPromptVersionListResponse(BaseModel):
    """Ответ списка версий с курсорной пагинацией."""

    items: list[SystemPromptVersionListItem]
    next_cursor: int | None = Field(
        default=None,
        description="version_number для следующей порции. null = больше данных нет.",
    )


class SystemPromptVersionActivate(BaseModel):
    """Ответ при активации версии."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    version_number: int
    is_active: bool
    activated_at: datetime
