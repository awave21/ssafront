"""Приведение каталога возможностей к тому, что бэкенд действительно исполняет.

Список действий приходит из фронтенда — так помощник видит ровно те карточки,
что есть у пользователя на экране. Но доверять этому списку целиком нельзя:
если фронтенд обгонит бэкенд (или отстанет), помощник начнёт советовать
действие, которого раннер не знает. Поэтому пересекаем с ActionType — единственным
списком, по которому правило вообще сохранится.
"""
from __future__ import annotations

from typing import get_args

from app.schemas.agent_assistant import AssistantCatalogItem
from app.schemas.function_rule import ActionType

SUPPORTED_ACTION_TYPES: frozenset[str] = frozenset(get_args(ActionType))


def sanitize_actions(items: list[AssistantCatalogItem]) -> list[AssistantCatalogItem]:
    """Оставить только действия, которые бэкенд умеет исполнять.

    Заодно отсекает карточки-заглушки «Скоро» (`soon_*`): их значения в enum
    не входят, поэтому фильтр по SUPPORTED_ACTION_TYPES убирает их сам.
    """
    seen: set[str] = set()
    allowed: list[AssistantCatalogItem] = []
    for item in items:
        value = (item.value or "").strip()
        if value not in SUPPORTED_ACTION_TYPES or value in seen:
            continue
        seen.add(value)
        allowed.append(item)
    return allowed


def known_preset_ids(items: list[AssistantCatalogItem]) -> set[str]:
    """Идентификаторы заготовок, по которым фронтенд умеет открыть конструктор."""
    return {(item.value or "").strip() for item in items if (item.value or "").strip()}


def render_catalog(title: str, items: list[AssistantCatalogItem]) -> str:
    if not items:
        return f"## {title}\nНичего не доступно."
    lines = [f"## {title}"]
    lines.extend(
        f"- `{item.value}` — {item.label}" + (f": {item.description}" if item.description else "")
        for item in items
    )
    return "\n".join(lines)
