from __future__ import annotations

from typing import Any

import structlog
from pydantic_ai.messages import (
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)

from app.db.models.agent import Agent
from app.core.config import get_settings

logger = structlog.get_logger("app.services.runtime")

# part_kind, при которых сообщение сериализуется в role="tool" для OpenAI API
_TOOL_ROLE_PART_KINDS = frozenset({
    "tool-call", "tool_call",
    "tool-return", "tool_return",
    "retry-prompt", "retry_prompt",
})


def _has_tool_role_parts(msg: Any) -> bool:
    """Содержит ли сообщение части, которые при сериализации дадут role='tool' или tool_calls."""
    if not (hasattr(msg, "parts") and isinstance(msg.parts, (list, tuple))):
        return False
    return any(
        getattr(p, "part_kind", None) in _TOOL_ROLE_PART_KINDS
        or isinstance(p, (ToolCallPart, ToolReturnPart, RetryPromptPart))
        for p in msg.parts
    )


def prepare_message_history(
    agent: Agent,
    message_history: list[Any] | None,
    trace_id: str,
) -> list[Any] | None:
    """Подготовить историю для pydantic-ai:
    1. Убрать system-prompt части (safety-net для старых DB-записей;
       при использовании instructions pydantic-ai делает это сам).
    2. Применить политику runtime_strip_tool_messages_from_history.
    3. Пропустить orphaned tool-return без соответствующего tool-call.
    4. Если после фильтрации остались непарные tool-call — убрать все tool-сообщения.
    """
    if not message_history:
        return message_history

    # --- Шаг 1: убрать legacy system-prompt части из истории ---
    cleaned: list[Any] = []
    removed_system_prompts = 0
    for msg in message_history:
        if hasattr(msg, "parts") and isinstance(msg.parts, (list, tuple)):
            new_parts = [p for p in msg.parts if getattr(p, "part_kind", None) != "system-prompt"]
            removed_system_prompts += len(msg.parts) - len(new_parts)
            if new_parts:
                msg.parts = new_parts
                cleaned.append(msg)
        else:
            cleaned.append(msg)

    if removed_system_prompts:
        logger.info(
            "legacy_system_prompts_removed_from_history",
            agent_id=str(agent.id),
            removed_count=removed_system_prompts,
        )

    # --- Шаг 2: политика strip_tool_messages ---
    settings = get_settings()
    if settings.runtime_strip_tool_messages_from_history:
        before = len(cleaned)
        cleaned = [msg for msg in cleaned if not _has_tool_role_parts(msg)]
        if len(cleaned) < before:
            logger.info(
                "tool_messages_stripped_by_policy",
                trace_id=trace_id,
                removed_count=before - len(cleaned),
            )

    # --- Шаг 3: валидация tool-call/tool-return пар ---
    validated: list[Any] = []
    pending: dict[str, Any] = {}
    in_tool_block = False

    for i, msg in enumerate(cleaned):
        if not (hasattr(msg, "parts") and isinstance(msg.parts, (list, tuple))):
            in_tool_block = False
            validated.append(msg)
            continue

        has_calls = False
        has_returns = False
        for part in msg.parts:
            pk = getattr(part, "part_kind", None)
            if pk in ("tool-call", "tool_call") or isinstance(part, ToolCallPart):
                has_calls = True
                tid = getattr(part, "tool_call_id", None) or getattr(part, "id", None)
                if tid:
                    pending[str(tid)] = part
            elif (
                pk in ("tool-return", "tool_return", "retry-prompt", "retry_prompt")
                or isinstance(part, (ToolReturnPart, RetryPromptPart))
            ):
                has_returns = True
                tid = getattr(part, "tool_call_id", None) or getattr(part, "id", None)
                if tid:
                    pending.pop(str(tid), None)

        if has_calls:
            in_tool_block = True
            validated.append(msg)
        elif has_returns:
            if not in_tool_block:
                logger.warning(
                    "orphaned_tool_return_skipped",
                    trace_id=trace_id,
                    message_index=i,
                    message_type=type(msg).__name__,
                )
                continue
            validated.append(msg)
        else:
            in_tool_block = False
            validated.append(msg)

    # --- Шаг 4: если остались непарные tool-call — безопасный фолбек ---
    if pending:
        logger.warning(
            "unmatched_tool_calls_fallback",
            trace_id=trace_id,
            unmatched_count=len(pending),
            tool_call_ids=list(pending.keys()),
            action="stripping_all_tool_messages",
        )
        before = len(validated)
        validated = [msg for msg in validated if not _has_tool_role_parts(msg)]
        logger.info(
            "tool_messages_removed_from_history",
            trace_id=trace_id,
            original_count=before,
            safe_count=len(validated),
        )

    return validated
