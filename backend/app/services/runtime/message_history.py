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
    # Keep history structurally valid for pydantic-ai:
    # tool-call/tool-return pairs must stay consistent after filtering.
    if not message_history:
        return message_history

    logger.info(
        "filtering_system_prompts_from_history",
        agent_id=str(agent.id),
        history_length=len(message_history),
    )

    filtered_history = []
    removed_system_prompts = 0
    for msg in message_history:
        if hasattr(msg, "parts") and isinstance(msg.parts, (list, tuple)):
            old_parts_count = len(msg.parts)
            new_parts = [p for p in msg.parts if getattr(p, "part_kind", None) != "system-prompt"]
            removed_count = old_parts_count - len(new_parts)
            removed_system_prompts += removed_count
            if new_parts:
                msg.parts = new_parts
                filtered_history.append(msg)
        else:
            filtered_history.append(msg)

    logger.info(
        "system_prompts_filtered",
        agent_id=str(agent.id),
        removed_system_prompts=removed_system_prompts,
        filtered_history_length=len(filtered_history),
    )

    settings = get_settings()
    if settings.runtime_strip_tool_messages_from_history:
        safe_history = [msg for msg in filtered_history if not _has_tool_role_parts(msg)]
        if len(safe_history) < len(filtered_history):
            logger.info(
                "tool_messages_stripped_by_policy",
                trace_id=trace_id,
                original_count=len(filtered_history),
                safe_count=len(safe_history),
                removed_count=len(filtered_history) - len(safe_history),
            )
        filtered_history = safe_history

    validated_history: list[Any] = []
    pending_tool_calls: dict[str, list] = {}
    tool_call_count = 0
    tool_return_count = 0
    in_tool_block = False

    for i, msg in enumerate(filtered_history):
        if hasattr(msg, "parts") and isinstance(msg.parts, (list, tuple)):
            has_tool_calls = False
            has_tool_returns = False
            for part in msg.parts:
                pk = getattr(part, "part_kind", None)
                if pk in ("tool-call", "tool_call") or isinstance(part, ToolCallPart):
                    has_tool_calls = True
                    tool_call_count += 1
                    tid = getattr(part, "tool_call_id", None) or getattr(part, "id", None)
                    if tid:
                        pending_tool_calls[str(tid)] = []
                elif (
                    pk in ("tool-return", "tool_return", "retry-prompt", "retry_prompt")
                    or isinstance(part, (ToolReturnPart, RetryPromptPart))
                ):
                    has_tool_returns = True
                    tool_return_count += 1
                    tid = getattr(part, "tool_call_id", None) or getattr(part, "id", None)
                    if tid and str(tid) in pending_tool_calls:
                        del pending_tool_calls[str(tid)]

            if has_tool_calls:
                in_tool_block = True
                validated_history.append(msg)
            elif has_tool_returns and not has_tool_calls:
                if not in_tool_block:
                    logger.warning(
                        "orphaned_tool_return_skipped",
                        trace_id=trace_id,
                        message_index=i,
                        message_type=type(msg).__name__,
                        reason="tool block not active (gap or truncated history)",
                    )
                    continue
                validated_history.append(msg)
            else:
                in_tool_block = False
                validated_history.append(msg)
        else:
            in_tool_block = False
            validated_history.append(msg)

    if pending_tool_calls:
        logger.warning(
            "unmatched_tool_calls_in_history",
            trace_id=trace_id,
            unmatched_count=len(pending_tool_calls),
            tool_call_ids=list(pending_tool_calls.keys()),
        )

    v_tool_call_count = 0
    v_tool_return_count = 0
    v_pending: dict[str, list] = {}
    for msg in validated_history:
        if not (hasattr(msg, "parts") and isinstance(msg.parts, (list, tuple))):
            continue
        for part in msg.parts:
            pk = getattr(part, "part_kind", None)
            if pk in ("tool-call", "tool_call") or isinstance(part, ToolCallPart):
                v_tool_call_count += 1
                tid = getattr(part, "tool_call_id", None) or getattr(part, "id", None)
                if tid:
                    v_pending[str(tid)] = []
            elif (
                pk in ("tool-return", "tool_return", "retry-prompt", "retry_prompt")
                or isinstance(part, (ToolReturnPart, RetryPromptPart))
            ):
                v_tool_return_count += 1
                tid = getattr(part, "tool_call_id", None) or getattr(part, "id", None)
                if tid and str(tid) in v_pending:
                    del v_pending[str(tid)]

    final_history: list[Any] = validated_history
    if v_pending or v_tool_return_count > v_tool_call_count:
        logger.warning(
            "message_history_structure_issues_detected",
            trace_id=trace_id,
            action="removing_tool_related_messages",
            original_length=len(validated_history),
            v_pending_count=len(v_pending),
            v_tool_calls=v_tool_call_count,
            v_tool_returns=v_tool_return_count,
        )
        safe_history = [
            msg for msg in validated_history
            if not _has_tool_role_parts(msg)
        ]
        if len(safe_history) < len(validated_history):
            logger.info(
                "tool_messages_removed_from_history",
                trace_id=trace_id,
                original_count=len(validated_history),
                safe_count=len(safe_history),
                removed_count=len(validated_history) - len(safe_history),
            )
        final_history = safe_history

    return final_history
