"""Помощник-конструктор: подсказывает, как собрать агента, и ничего не меняет."""
from app.services.agent_assistant.catalog import (
    SUPPORTED_ACTION_TYPES,
    known_preset_ids,
    sanitize_actions,
)
from app.services.agent_assistant.activity import build_activity_snapshot, render_activity
from app.services.agent_assistant.context import build_agent_snapshot, render_snapshot
from app.services.agent_assistant.service import (
    AssistantOutput,
    AssistantRunResult,
    run_assistant,
)

__all__ = [
    "SUPPORTED_ACTION_TYPES",
    "AssistantOutput",
    "AssistantRunResult",
    "build_activity_snapshot",
    "build_agent_snapshot",
    "render_activity",
    "known_preset_ids",
    "render_snapshot",
    "run_assistant",
    "sanitize_actions",
]
