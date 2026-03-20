"""
History processors для управления контекстом в диалогах с агентами.

Используют механизм history_processors из pydantic-ai для:
- Ограничения количества сообщений (sliding window)
- Суммаризации старых сообщений через дешёвую LLM (сохранение контекста)
- Сохранения пар tool-call/tool-return

Подход соответствует официальной документации Pydantic AI:
https://ai.pydantic.dev/message-history/#summarize-old-messages
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)

logger = structlog.get_logger(__name__)


def keep_recent_messages_with_tool_pairs(
    messages: list[ModelMessage],
    max_messages: int = 50,
) -> list[ModelMessage]:
    """
    Sliding window с сохранением пар tool-call/tool-return.

    Обрезает историю, оставляя последние N сообщений, но следит за тем,
    чтобы не разорвать пары tool call -> tool return.

    Args:
        messages: История сообщений
        max_messages: Максимальное количество сообщений

    Returns:
        Обрезанная история
    """
    if len(messages) <= max_messages:
        return messages

    # Начинаем с последних max_messages
    candidate_messages = messages[-max_messages:]

    # Проверяем первое сообщение — если это tool-return без tool-call,
    # включаем предыдущее сообщение (с tool calls)
    if candidate_messages and isinstance(candidate_messages[0], ModelRequest):
        first_msg = candidate_messages[0]
        if hasattr(first_msg, "parts"):
            has_tool_returns = any(
                isinstance(p, ToolReturnPart) for p in first_msg.parts
            )
            if has_tool_returns:
                start_idx = len(messages) - max_messages
                if start_idx > 0:
                    candidate_messages = [messages[start_idx - 1]] + candidate_messages

    logger.info(
        "message_history_trimmed",
        original_count=len(messages),
        kept_count=len(candidate_messages),
        max_messages=max_messages,
    )

    return candidate_messages


def _build_summary_instructions(agent_context: str | None) -> str:
    """
    Построить инструкцию для суммаризатора.

    Если агент задал кастомный `summary_prompt` — использует его напрямую.
    Иначе — генерирует универсальную инструкцию, опционально обогащённую
    первыми строками системного промпта агента для доменного контекста.
    """
    if agent_context and agent_context.strip():
        return agent_context.strip()

    return (
        "Сожми историю диалога в компактный блок памяти на языке диалога.\n"
        "Сохрани все фактические данные: имена, ID, даты, числа, статусы, "
        "результаты вызовов инструментов. Не придумывай недостающие детали.\n"
        "Структура:\n"
        "1) ПОЛЬЗОВАТЕЛЬ: ключевые данные о пользователе.\n"
        "2) КОНТЕКСТ: сущности диалога (заказы, записи, заявки, товары и т.д.).\n"
        "3) СДЕЛАНО: завершённые действия и их результаты.\n"
        "4) ОТКРЫТО: нерешённые вопросы или ожидающие ответа пункты.\n"
        "5) ДАЛЕЕ: что агенту нужно сделать следующим.\n"
        "Если секция пуста — напиши «нет данных». "
        "Будь краток, но полон: 8–15 коротких строк."
    )


async def summarize_old_messages(
    messages: list[ModelMessage],
    *,
    max_messages: int = 50,
    summary_model: str | None = None,
    openai_api_key: str | None = None,
    agent_context: str | None = None,
) -> list[ModelMessage]:
    """
    Суммаризация старых сообщений через дешёвую LLM.

    Паттерн из документации Pydantic AI:
    - Если сообщений > max_messages, берём старые и делаем summary
    - Возвращаем [summary] + [последние сообщения]

    Args:
        messages: Полная история сообщений
        max_messages: Порог, после которого включается summary
        summary_model: Модель для суммаризации
        agent_context: Кастомный промпт суммаризатора из настроек агента.
                       Если None — используется универсальный шаблон.

    Returns:
        Обработанная история: [summary_messages] + [recent_messages]
    """
    if len(messages) <= max_messages:
        return messages

    try:
        from pydantic_ai import Agent as PydanticAgent
    except ImportError:
        logger.warning("pydantic_ai_not_available_for_summary")
        return messages

    old_messages = messages[:-max_messages]
    recent_messages = messages[-max_messages:]

    if not old_messages:
        return messages

    logger.info(
        "summarizing_old_messages",
        old_count=len(old_messages),
        recent_count=len(recent_messages),
        total_count=len(messages),
    )

    try:
        from app.core.config import get_settings
        from app.services.runtime.model_resolver import resolve_model

        effective_model = summary_model or get_settings().summary_model
        resolved = resolve_model(effective_model, openai_api_key=openai_api_key)
        instructions = _build_summary_instructions(agent_context)
        summary_agent = PydanticAgent(resolved, instructions=instructions)

        summary_result = await summary_agent.run(
            "Summarize the previous conversation into a structured memory block.",
            message_history=old_messages,
        )

        summary_messages = summary_result.new_messages()

        logger.info(
            "summary_created",
            old_messages_count=len(old_messages),
            summary_messages_count=len(summary_messages),
        )

        return summary_messages + recent_messages

    except Exception as e:
        logger.warning(
            "summary_failed_fallback_to_sliding_window",
            error=str(e),
        )
        fallback_max_messages = max(max_messages * 3, 30)
        return keep_recent_messages_with_tool_pairs(messages, fallback_max_messages)


def create_history_processor(
    max_messages: int = 50,
    enable_summary: bool = True,
    summary_model: str | None = None,
    openai_api_key: str | None = None,
    agent_context: str | None = None,
) -> list:
    """
    Создать список history processors для агента.

    Стратегия (по документации Pydantic AI):
    1. Если сообщений > max_messages и summary включён:
       старые → LLM summary, новые → как есть
    2. Если summary выключен или не удался:
       sliding window — последние max_messages сообщений

    Args:
        max_messages: Порог для summary / размер sliding window
        enable_summary: Включить суммаризацию через LLM
        summary_model: Модель для суммаризации
        agent_context: Кастомный промпт суммаризатора (из agent.summary_prompt
                       или первых строк agent.system_prompt).

    Returns:
        Список processors для передачи в Agent(..., history_processors=...)
    """
    if enable_summary:
        async def processor(messages: list[ModelMessage]) -> list[ModelMessage]:
            return await summarize_old_messages(
                messages,
                max_messages=max_messages,
                summary_model=summary_model,
                openai_api_key=openai_api_key,
                agent_context=agent_context,
            )

        return [processor]

    def processor_sync(messages: list[ModelMessage]) -> list[ModelMessage]:
        return keep_recent_messages_with_tool_pairs(messages, max_messages)

    return [processor_sync]
