"""
Runtime package — оркестрация запуска AI-агентов.

Re-exports для обратной совместимости:
    from app.services.runtime import run_agent_with_tools, AgentRunResult
    from app.services.runtime import messages_adapter
"""

from app.services.runtime.orchestrator import (
    AgentRunResult,
    logger,
    messages_adapter,
    run_agent_with_tools,
)

__all__ = [
    "AgentRunResult",
    "logger",
    "messages_adapter",
    "run_agent_with_tools",
]
