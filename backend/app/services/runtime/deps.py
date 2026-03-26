"""
Зависимости (deps) для pydantic-ai агентов.

Передаются через agent.run(deps=AgentDeps(...)) и доступны
в tool-функциях через ctx.deps — без повторных DB-запросов внутри tool.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class AgentDeps:
    """
    Контекст одного запуска агента.

    Поля передаются один раз в Agent.run() и доступны в любом tool
    через RunContext[AgentDeps].deps.

    openai_api_key  — API-ключ тенанта (уже расшифрован).
                      Позволяет избежать SELECT + decrypt при каждом
                      семантическом поиске внутри tool.
    tenant_id       — UUID тенанта для billing/logging внутри tool.
    extra           — произвольные данные (session_id, run_id и т.п.)
                      для будущих расширений без изменения сигнатуры.
    """

    openai_api_key: str | None = None
    tenant_id: UUID | None = None
    extra: dict[str, Any] = field(default_factory=dict)
