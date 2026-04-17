"""Сборка optional runtime data-тулов (knowledge, direct questions, directories).

Раньше модуль отсутствовал в репозитории, но импортировался из run_service — без него API не стартует.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic_ai.tools import Tool as PydanticTool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.agent import Agent
from app.services.runtime.tools import (
    build_direct_answer_tool,
    build_direct_questions_search_tool,
    build_directory_runtime_tools,
    build_knowledge_search_tool,
)


@dataclass
class OptionalRuntimeToolsBundle:
    tools: list[PydanticTool]
    retrieval_decisions: list[dict[str, Any]]
    system_prompt_addition: str | None = None


async def build_optional_runtime_tools(
    *,
    db: AsyncSession,
    agent: Agent,
    tenant_id: UUID,
    session_id: str,
    selected_categories: set[str],
    settings: Settings,
    openai_api_key: str | None,
) -> OptionalRuntimeToolsBundle:
    """
    Подключает data-тулы по выбранным категориям (см. context_assembler).

    `retrieval_decisions` — тот же список, что передаётся в search_direct_questions
    как analytics_sink: заполняется во время выполнения агента, не при сборке.
    """
    del session_id  # зарезервировано для будущих сценариев / expertise bridge

    tools: list[PydanticTool] = []
    retrieval_decisions: list[dict[str, Any]] = []

    if "knowledge" in selected_categories:
        kt = await build_knowledge_search_tool(
            db=db,
            tenant_id=tenant_id,
            agent_id=agent.id,
            openai_api_key=openai_api_key,
            description=agent.knowledge_tool_description,
        )
        if kt is not None:
            tools.append(kt)

    if "direct_questions" in selected_categories and settings.direct_questions_retrieval_router_enabled:
        tools.append(
            build_direct_questions_search_tool(
                db=db,
                tenant_id=tenant_id,
                agent_id=agent.id,
                openai_api_key=openai_api_key,
                default_limit=settings.direct_questions_max_results,
                min_match_percent=settings.direct_questions_min_match_percent,
                rerank=settings.direct_questions_rerank_enabled,
                analytics_sink=retrieval_decisions,
            )
        )
        tools.append(
            build_direct_answer_tool(
                db=db,
                tenant_id=tenant_id,
                agent_id=agent.id,
            )
        )

    if "directory" in selected_categories:
        dir_tools = await build_directory_runtime_tools(
            db=db,
            agent_id=agent.id,
            openai_api_key=openai_api_key,
        )
        tools.extend(dir_tools)

    # expertise: поиск по индексированным скриптам (get_expertise) может быть добавлен позже;
    # сейся сценарная экспертиза уходит через augment_prompt / диалоговые фазы.

    return OptionalRuntimeToolsBundle(
        tools=tools,
        retrieval_decisions=retrieval_decisions,
        system_prompt_addition=None,
    )
