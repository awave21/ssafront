from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import logfire
import structlog
from pydantic import TypeAdapter
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, RetryPromptPart, ToolCallPart, ToolReturnPart
from pydantic_ai.tools import Tool as PydanticTool
from pydantic_ai.usage import UsageLimits

from app.core.config import get_settings
from app.db.models.agent import Agent
from app.db.models.binding import AgentToolBinding
from app.db.models.tool import Tool
from app.schemas.auth import AuthContext
from app.services.runtime.history_processors import create_history_processor
from app.services.runtime.agent_builder import _build_agent
from app.services.runtime.message_history import prepare_message_history
from app.services.runtime.sqns import prepare_sqns_tooling
from app.services.runtime.token_usage import extract_token_usage
from app.services.runtime.tool_calls import extract_tools_called
from app.services.runtime.tools import _build_tool_wrapper, build_directory_tools
from app.services.runtime.utils import _enrich_system_prompt_with_datetime, _sanitize_output

logger = structlog.get_logger(__name__)

# Типы, которые реально возвращает pydantic-ai в new_messages() / all_messages()
messages_adapter = TypeAdapter(list[ModelMessage | ModelRequest | ModelResponse])


@dataclass
class AgentRunResult:
    """Результат одного запуска агента."""

    output: str
    new_messages: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    token_usage_steps: list[dict[str, Any]] = field(default_factory=list)
    tools_called: list[dict[str, Any]] = field(default_factory=list)
    tool_call_events: list[dict[str, Any]] = field(default_factory=list)
    orchestration_meta: dict[str, Any] | None = None


async def run_agent_with_tools(
    agent: Agent,
    tools: list[Tool],
    bindings: list[AgentToolBinding],
    *,
    input_message: str,
    trace_id: str,
    user: AuthContext,
    message_history: list[Any] | None = None,
    run_id: UUID | None = None,
    session_id: str | None = None,
    openai_api_key: str | None = None,
    system_prompt_override: str | None = None,
    extra_tools: list[PydanticTool] | None = None,
) -> AgentRunResult:
    settings = get_settings()
    model_name = agent.model or settings.pydanticai_default_model
    
    # Фолбек для некорректного имени модели "string" (часто дефолт в Swagger UI)
    if model_name == "string":
        logger.warning(
            "invalid_model_name_fallback",
            agent_id=str(agent.id),
            original_model=model_name,
            fallback_model=settings.pydanticai_default_model
        )
        model_name = settings.pydanticai_default_model
    
    # Подготовка тулов: собираем обычные
    binding_map = {binding.tool_id: binding for binding in bindings}
    wrapped_tools: list[PydanticTool] = []
    tool_events: list[dict[str, Any]] = []
    for tool in tools:
        binding = binding_map.get(tool.id)
        if not binding:
            continue
        # _build_tool_wrapper теперь возвращает готовый PydanticTool
        pydantic_tool = _build_tool_wrapper(
            tool,
            binding,
            agent_id=agent.id,
            session_id=session_id,
            trace_id=trace_id,
            user=user,
            tool_events=tool_events,
        )
        wrapped_tools.append(pydantic_tool)
    
    directory_tools = await build_directory_tools(agent.id)
    if directory_tools:
        wrapped_tools.extend(directory_tools)

    sqns_toolsets, sqns_tools = await prepare_sqns_tooling(agent, user)
    if sqns_tools:
        wrapped_tools.extend(sqns_tools)
    if extra_tools:
        wrapped_tools.extend(extra_tools)
    
    # Определяем контекст для суммаризатора:
    # приоритет — кастомный summary_prompt агента,
    # иначе — первые 500 символов system_prompt для доменного контекста.
    agent_summary_context: str | None = None
    if getattr(agent, "summary_prompt", None):
        agent_summary_context = agent.summary_prompt
    elif agent.system_prompt:
        agent_summary_context = agent.system_prompt[:500]

    history_processors = create_history_processor(
        max_messages=agent.max_history_messages or 50,
        enable_summary=True,
        summary_model=settings.summary_model,
        openai_api_key=openai_api_key,
        agent_context=agent_summary_context,
    )
    
    # Собираем агента с tools и toolsets
    # Обогащаем системный промпт переменными даты и времени
    base_system_prompt = system_prompt_override if system_prompt_override is not None else agent.system_prompt
    enriched_system_prompt = _enrich_system_prompt_with_datetime(base_system_prompt, agent.timezone)
    pydantic_agent = _build_agent(
        model_name,
        enriched_system_prompt,
        agent.llm_params or {},
        tools=wrapped_tools if wrapped_tools else None,
        toolsets=sqns_toolsets if sqns_toolsets else None,
        history_processors=history_processors,
        openai_api_key=openai_api_key,
    )
    
    # Логирование для отладки
    sqns_tool_names = [t.name for t in wrapped_tools if t.name.startswith("sqns_")] if wrapped_tools else []
    logger.info(
        "agent_created_with_tools",
        agent_id=str(agent.id),
        total_tools=len(wrapped_tools),
        total_toolsets=len(sqns_toolsets),
        tool_names=[t.name for t in wrapped_tools] if wrapped_tools else [],
        sqns_approach="fastmcp_toolset" if sqns_toolsets else ("legacy_tools" if sqns_tool_names else "none"),
        sqns_tool_count=len(sqns_tool_names),
    )

    if message_history:
        message_history = prepare_message_history(
            agent,
            message_history,
            trace_id,
        )

    # Логируем историю сообщений, которая уйдет в модель (для отладки)
    # Проверяем структуру сообщений перед отправкой
    if message_history:
        tool_call_count = 0
        tool_return_count = 0
        for msg in message_history:
            if hasattr(msg, "parts") and isinstance(msg.parts, (list, tuple)):
                for part in msg.parts:
                    part_kind = getattr(part, "part_kind", None)
                    if part_kind in ("tool-call", "tool_call") or isinstance(part, ToolCallPart):
                        tool_call_count += 1
                    elif (
                        part_kind in ("tool-return", "tool_return", "retry-prompt", "retry_prompt")
                        or isinstance(part, (ToolReturnPart, RetryPromptPart))
                    ):
                        tool_return_count += 1
        
        logger.info(
            "before_agent_run",
            agent_id=str(agent.id),
            trace_id=trace_id,
            has_message_history=True,
            message_history_length=len(message_history),
            tool_calls_in_history=tool_call_count,
            tool_returns_in_history=tool_return_count,
            message_types=[type(m).__name__ for m in message_history[:5]],  # Первые 5 типов для отладки
        )
    else:
        logger.info(
            "before_agent_run",
            agent_id=str(agent.id),
            trace_id=trace_id,
            has_message_history=False,
            message_history_length=0,
        )
    
    span_attributes: dict[str, Any] = {
        "trace_id": trace_id,
        "agent_id": str(agent.id),
        "model_name": model_name,
    }
    if run_id is not None:
        span_attributes["run_id"] = str(run_id)
    if session_id:
        span_attributes["session_id"] = session_id

    try:
        span_context = logfire.span("agent_run", **span_attributes)
    except Exception:
        span_context = nullcontext()

    # Per-agent лимиты переопределяют глобальные настройки платформы.
    effective_tool_calls_limit = getattr(agent, "max_tool_calls", None) or settings.runtime_tool_calls_limit
    # request_limit = tool_calls_limit + 1 (последний запрос для финального ответа)
    effective_request_limit = max(effective_tool_calls_limit + 1, settings.runtime_request_limit)

    with span_context:
        result = await pydantic_agent.run(
            input_message,
            message_history=message_history,
            usage_limits=UsageLimits(
                tool_calls_limit=effective_tool_calls_limit,
                request_limit=effective_request_limit,
            ),
        )
    output = getattr(result, "data", None)
    if output is None:
        output = str(result)
    elif hasattr(output, "output"):
        output = getattr(output, "output", output)
    if not isinstance(output, str):
        output = str(output)
    output = _sanitize_output(output)
    
    new_messages = result.new_messages()
    all_messages_count: int | None = None
    try:
        all_messages = result.all_messages() if hasattr(result, "all_messages") else None
        if isinstance(all_messages, list):
            all_messages_count = len(all_messages)
    except Exception:
        all_messages_count = None
    logger.info(
        "run_message_boundary",
        trace_id=trace_id,
        new_messages_count=len(new_messages),
        all_messages_count=all_messages_count,
    )
    new_messages_json = messages_adapter.dump_python(new_messages, mode="json")
    
    prompt_tokens, completion_tokens, total_tokens, token_usage_steps = extract_token_usage(
        result,
        new_messages,
        trace_id,
        model_name,
    )
    
    tools_called = extract_tools_called(result, new_messages, trace_id)
    
    if tools_called:
        logger.info(
            "tools_called_extracted",
            trace_id=trace_id,
            tools_count=len(tools_called),
            tool_names=[t["name"] for t in tools_called]
        )
    
    # Логируем, если системный промпт оказался в ответе
    system_prompt_found = False
    for msg in new_messages:
        if hasattr(msg, "parts"):
            for part in msg.parts:
                if getattr(part, "part_kind", None) == "system-prompt":
                    system_prompt_found = True
                    system_prompt_content = getattr(part, "content", "")[:100]
                    logger.info(
                        "system_prompt_in_response",
                        trace_id=trace_id,
                        system_prompt_preview=system_prompt_content
                    )
                    break
    
    if not system_prompt_found and message_history and len(message_history) == 0:
        logger.warning(
            "no_system_prompt_in_first_message",
            trace_id=trace_id,
            agent_id=str(agent.id),
            expected_system_prompt=agent.system_prompt[:100] if agent.system_prompt else ""
        )
    
    logger.info("run_completed", trace_id=trace_id)
    return AgentRunResult(
        output=str(output),
        new_messages=new_messages_json,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        token_usage_steps=token_usage_steps,
        tools_called=tools_called,
        tool_call_events=tool_events,
    )
