"""Схемы помощника-конструктора — чата, который подсказывает, как собрать агента.

Каталог возможностей (действия, заготовки) приходит из фронтенда вместе с
вопросом. Так помощник всегда знает ровно то, что у пользователя есть в
интерфейсе прямо сейчас: второй копии списка действий на бэкенде не заводим —
разъезжаться будет нечему.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SuggestionKind = Literal["function", "scenario", "table", "knowledge", "prompt", "channel"]


class AssistantMessage(BaseModel):
    """Одна реплика в истории переписки с помощником."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class AssistantCatalogItem(BaseModel):
    """Пункт каталога возможностей: действие правила или готовая заготовка."""

    value: str = Field(max_length=120, description="Код действия или id заготовки")
    label: str = Field(max_length=200)
    description: str = Field(default="", max_length=400)


class AssistantChatRequest(BaseModel):
    """Вопрос пользователя вместе со снимком того, что умеет его интерфейс."""

    message: str = Field(min_length=1, max_length=4000)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=20)
    actions: list[AssistantCatalogItem] = Field(default_factory=list, max_length=40)
    function_presets: list[AssistantCatalogItem] = Field(default_factory=list, max_length=40)
    scenario_presets: list[AssistantCatalogItem] = Field(default_factory=list, max_length=40)
    model: str | None = Field(default=None, max_length=200)


class AssistantSuggestion(BaseModel):
    """Предложение помощника — куда перейти, чтобы это настроить.

    Помощник ничего не создаёт сам: он выдаёт карточку, а переход и сохранение
    остаются за человеком.
    """

    kind: SuggestionKind
    title: str = Field(max_length=120)
    rationale: str = Field(default="", max_length=400)
    preset_id: str | None = Field(default=None, max_length=120)


class AssistantChatResponse(BaseModel):
    """Ответ помощника: текст в Markdown плюс карточки-переходы."""

    message: str
    suggestions: list[AssistantSuggestion] = Field(default_factory=list)
    followups: list[str] = Field(default_factory=list)
    model: str
