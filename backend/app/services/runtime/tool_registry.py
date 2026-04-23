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
from app.services.runtime.diagnose_tool import (
    DIAGNOSE_PROMPT_BRIDGE,
    build_diagnose_client_motive_tool,
)
from app.services.runtime.motive_state import (
    is_state_empty,
    load_motive_state,
    render_state_snapshot,
)
from app.services.runtime.script_flow_tool import (
    SCRIPT_FLOWS_PROMPT_BRIDGE,
    build_script_flows_search_tool,
)
from app.services.runtime.tools import (
    build_direct_answer_tool,
    build_direct_questions_search_tool,
    build_directory_runtime_tools,
    build_knowledge_search_tool,
)
from sqlalchemy import select
from app.db.models.agent_kg_entity import AgentKgEntity


def _render_tactic_style_as_law(style: dict[str, Any]) -> str:
    """Форматирует стиль последнего сработавшего экспертного сценария как
    обязательную секцию системного промпта.

    Это «закон» — LLM обязана следовать ему независимо от того, вызвала ли
    она search_script_flows в текущем ходу или нет.
    Секция обновляется каждый раз, когда поиск находит новый топ-матч.
    """
    lines: list[str] = []
    tactic = style.get("tactic_title") or ""
    flow = style.get("flow_name") or ""
    label = f" (сценарий: {tactic})" if tactic else (f" (поток: {flow})" if flow else "")
    lines.append(f"=== СТИЛЬ ЭКСПЕРТА{label} — ОБЯЗАТЕЛЬНО ===")
    lines.append("Отвечай как живой человек, не как система или внутренний регламент.")
    lines.append("Не озвучивай внутреннюю логику, поиск, категории услуг, позиции в системе и маршрутизацию.")

    comm = (style.get("communication_style") or "").strip()
    if comm:
        lines.append(f"Тон и стиль ответа: {comm}")

    preferred: list[str] = [p for p in (style.get("preferred_phrases") or []) if str(p).strip()]
    if preferred:
        lines.append("Используй эти формулировки (адаптируй под контекст):")
        for p in preferred[:6]:
            lines.append(f"  • «{p}»")

    forbidden: list[str] = [p for p in (style.get("forbidden_phrases") or []) if str(p).strip()]
    if forbidden:
        lines.append("ЗАПРЕЩЕНО произносить:")
        for p in forbidden[:6]:
            lines.append(f"  • «{p}»")

    constraints: list[str] = [c for c in (style.get("hard_constraints") or []) if str(c).strip()]
    if constraints:
        lines.append("Жёсткие ограничения клиники (не нарушай):")
        for c in constraints[:4]:
            lines.append(f"  ❗ {c}")

    followup = (style.get("required_followup_question") or "").strip()
    if followup:
        lines.append(f"Задай дословно в конце ответа: «{followup}»")

    lines.append("=== /СТИЛЬ ЭКСПЕРТА ===")
    return "\n".join(lines)


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
    # session_id нужен для motive-aware тулов. Стараемся распарсить как UUID,
    # а если строка не является UUID (например "integration:…:<uuid>") —
    # деривируем детерминированный UUID через uuid5 по неймспейсу проекта,
    # чтобы интеграционные сессии тоже могли накапливать motive-state.
    session_uuid: UUID | None = None
    if session_id:
        try:
            session_uuid = UUID(str(session_id))
        except (ValueError, TypeError):
            import uuid as _uuid_mod
            _NS = _uuid_mod.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # URL namespace
            session_uuid = _uuid_mod.uuid5(_NS, str(session_id))

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

    # Экспертные потоки (Vue Flow → retriever) + motive-aware диагностика:
    # подключаются, если в выборке optional-категорий есть "expertise" или "script_flows".
    system_prompt_addition_parts: list[str] = []

    # "manual" — умолчание для новых агентов: пользователь пишет инструкции
    #            по инструментам сам в system_prompt. Никаких скрытых инжекций.
    # "auto"   — legacy-режим для старых агентов: bridge-тексты инжектируются
    #            автоматически (обратная совместимость).
    _bridges_auto = (getattr(agent, "runtime_bridges_mode", "manual") or "manual") == "auto"

    script_flow_tool = None
    diagnose_tool = None
    if "expertise" in selected_categories or "script_flows" in selected_categories:
        script_flow_tool = await build_script_flows_search_tool(
            db=db,
            agent_id=agent.id,
            tenant_id=tenant_id,
            session_id=session_uuid,
            openai_api_key=openai_api_key,
            strict_entry_default=bool(settings.runtime_script_flow_strict_entry_default),
        )
        if script_flow_tool is not None:
            tools.append(script_flow_tool)
            if _bridges_auto:
                system_prompt_addition_parts.append(SCRIPT_FLOWS_PROMPT_BRIDGE)

        diagnose_tool = await build_diagnose_client_motive_tool(
            db=db,
            agent_id=agent.id,
            tenant_id=tenant_id,
            session_id=session_uuid,
        )
        if diagnose_tool is not None:
            # Ставим в начало списка — LLM видит тулы сверху вниз, а diagnose
            # обязан вызываться первым.
            tools.insert(0, diagnose_tool)
            if _bridges_auto:
                system_prompt_addition_parts.insert(0, DIAGNOSE_PROMPT_BRIDGE)

    # Динамические блоки (стиль топ-тактики, snapshot диалога) — только в режиме
    # runtime_bridges_mode=auto. В manual пользователь видит ровно свой system_prompt;
    # состояние по-прежнему доступно в результатах инструментов и для rerank на сервере.
    if (
        _bridges_auto
        and session_uuid is not None
        and (script_flow_tool is not None or diagnose_tool is not None)
    ):
        state = await load_motive_state(
            db,
            session_id=session_uuid,
            agent_id=agent.id,
            tenant_id=tenant_id,
        )

        if state.last_tactic_style:
            system_prompt_addition_parts.append(
                _render_tactic_style_as_law(state.last_tactic_style)
            )

        if not is_state_empty(state):
            stmt = select(AgentKgEntity.id, AgentKgEntity.name).where(
                AgentKgEntity.agent_id == agent.id,
                AgentKgEntity.tenant_id == tenant_id,
            )
            rows = (await db.execute(stmt)).all()
            entity_names = {str(r[0]): r[1] for r in rows}
            system_prompt_addition_parts.append(
                render_state_snapshot(state, entity_names=entity_names)
            )

    system_prompt_addition: str | None = None
    if system_prompt_addition_parts:
        system_prompt_addition = "\n\n" + "\n\n".join(system_prompt_addition_parts)

    return OptionalRuntimeToolsBundle(
        tools=tools,
        retrieval_decisions=retrieval_decisions,
        system_prompt_addition=system_prompt_addition,
    )
