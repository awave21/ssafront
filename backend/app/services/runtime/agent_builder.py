from __future__ import annotations

from typing import Any
import inspect

import structlog
from pydantic_ai.tools import Tool as PydanticTool

from app.services.runtime.model_resolver import resolve_model

logger = structlog.get_logger("app.services.runtime")


def _build_agent(
    model_name: str,
    system_prompt: str,
    llm_params: dict[str, Any] | None,
    *,
    tools: list[PydanticTool] | None = None,
    toolsets: list[Any] | None = None,
    history_processors: list | None = None,
    openai_api_key: str | None = None,
):
    """
    Создать pydantic-ai Agent с правильными параметрами.

    Args:
        model_name: Название модели (например, 'openai:gpt-4.1', 'openai:gpt-4.1-mini')
        system_prompt: Системный промпт для агента
        llm_params: Параметры модели (temperature, max_tokens, etc)
        tools: Список pydantic-ai Tool объектов
        toolsets: Список toolsets (например, FastMCPToolset)
        history_processors: Список функций для обработки истории сообщений

    Returns:
        Настроенный pydantic-ai Agent
    """
    try:
        from pydantic_ai import Agent as PydanticAgent
    except ImportError as exc:
        raise RuntimeError("pydantic-ai is required for runtime execution") from exc

    signature = inspect.signature(PydanticAgent.__init__)
    agent_kwargs: dict[str, Any] = {}

    # В новых версиях pydantic-ai system_prompt может называться instructions.
    # Наше поле agent.system_prompt используется как единый управляющий слой
    # (роль/стиль/поведение) и маппится на доступный параметр конструктора.
    if "system_prompt" in signature.parameters:
        agent_kwargs["system_prompt"] = system_prompt
    elif "instructions" in signature.parameters:
        agent_kwargs["instructions"] = system_prompt

    # Добавить llm_params при наличии.
    if llm_params:
        if "model_settings" in signature.parameters:
            agent_kwargs["model_settings"] = llm_params
        elif "settings" in signature.parameters:
            agent_kwargs["settings"] = llm_params

    # Добавить tools при наличии.
    if tools:
        agent_kwargs["tools"] = tools

    # Добавить toolsets при наличии (FastMCP, MCP и т.д.).
    if toolsets:
        agent_kwargs["toolsets"] = toolsets

    # Добавить history_processors для управления контекстом
    if history_processors and "history_processors" in signature.parameters:
        agent_kwargs["history_processors"] = history_processors

    logger.info(
        "building_agent",
        model_name=model_name,
        has_system_prompt=bool(system_prompt),
        tools_count=len(tools) if tools else 0,
        toolsets_count=len(toolsets) if toolsets else 0,
        has_history_processors=bool(history_processors),
        agent_kwargs_keys=list(agent_kwargs.keys()),
        system_prompt_preview=system_prompt[:50] if system_prompt else "",
    )

    model = resolve_model(model_name, openai_api_key=openai_api_key)
    return PydanticAgent(model, **agent_kwargs)


def _attach_tools(agent: Any, tools: list[PydanticTool]) -> None:
    """
    Прикрепить pydantic-ai Tool объекты к агенту.

    Теперь используем правильные Tool объекты вместо функций.
    """
    if hasattr(agent, "add_tools"):
        agent.add_tools(tools)
        return
    if hasattr(agent, "tools") and isinstance(agent.tools, list):
        agent.tools.extend(tools)
        return
    raise RuntimeError("Unable to attach tools to agent")
