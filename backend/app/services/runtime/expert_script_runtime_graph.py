from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic_graph import BaseNode, End, Graph, GraphRunContext

from app.db.models.agent import Agent
from app.db.models.binding import AgentToolBinding
from app.db.models.tool import Tool
from app.schemas.auth import AuthContext
from app.services.runtime.orchestrator import AgentRunResult, run_agent_with_tools


def _has_runtime_tool(tools: list[Any] | None, tool_name: str) -> bool:
    if not tools:
        return False
    for tool in tools:
        name = getattr(tool, "name", None)
        if isinstance(name, str) and name == tool_name:
            return True
    return False


def _tools_called_has_name(tools_called: list[dict[str, Any]] | None, tool_name: str) -> bool:
    if not tools_called:
        return False
    for item in tools_called:
        if not isinstance(item, dict):
            continue
        if item.get("name") == tool_name:
            return True
    return False


def _is_greeting_only_message(text: str) -> bool:
    normalized = " ".join(str(text or "").strip().lower().split())
    if not normalized:
        return True
    greeting_tokens = {
        "привет",
        "здравствуйте",
        "добрый день",
        "доброе утро",
        "добрый вечер",
    }
    return normalized in greeting_tokens


def _build_force_script_flow_prompt(base_prompt: str | None) -> str:
    base = (base_prompt or "").rstrip()
    force_block = (
        "\n\n"
        "=== RUNTIME ENFORCEMENT: SCRIPT FLOW REQUIRED ===\n"
        "Перед финальным ответом ОБЯЗАТЕЛЬНО вызови `search_script_flows` для текущего сообщения клиента.\n"
        "Если нужна тактическая диагностика эмоции/возражения — сначала вызови `diagnose_client_motive`, затем `search_script_flows`.\n"
        "Ответ без вызова `search_script_flows` запрещен.\n"
        "=== /RUNTIME ENFORCEMENT ==="
    )
    return (base + force_block).strip() if base else force_block.strip()


@dataclass
class ExpertScriptRunState:
    agent: Agent
    tools: list[Tool]
    bindings: list[AgentToolBinding]
    input_message: str
    trace_id: str
    user: AuthContext
    message_history: list[Any] | None
    run_id: UUID | None
    session_id: str | None
    openai_api_key: str | None
    anthropic_api_key: str | None
    system_prompt_override: str | None
    extra_tools: list[Any] | None
    result: AgentRunResult | None = None
    retry_attempted: bool = False


@dataclass
class InitialModelRunNode(BaseNode[ExpertScriptRunState, None, AgentRunResult]):
    async def run(
        self,
        ctx: GraphRunContext[ExpertScriptRunState],
    ) -> "ScriptFlowRetryDecisionNode":
        state = ctx.state
        state.result = await run_agent_with_tools(
            state.agent,
            state.tools,
            state.bindings,
            input_message=state.input_message,
            trace_id=state.trace_id,
            user=state.user,
            message_history=state.message_history,
            run_id=state.run_id,
            session_id=state.session_id,
            openai_api_key=state.openai_api_key,
            anthropic_api_key=state.anthropic_api_key,
            system_prompt_override=state.system_prompt_override,
            extra_tools=state.extra_tools,
        )
        return ScriptFlowRetryDecisionNode()


@dataclass
class ScriptFlowRetryDecisionNode(BaseNode[ExpertScriptRunState, None, AgentRunResult]):
    async def run(
        self,
        ctx: GraphRunContext[ExpertScriptRunState],
    ) -> End[AgentRunResult] | "ForcedScriptFlowRetryNode":
        state = ctx.state
        result = state.result
        if result is None:
            raise RuntimeError("expert script runtime graph requires initial result")

        script_flow_available = _has_runtime_tool(state.extra_tools, "search_script_flows")
        script_flow_called = _tools_called_has_name(result.tools_called, "search_script_flows")
        should_retry = (
            not state.retry_attempted
            and script_flow_available
            and not script_flow_called
            and not _is_greeting_only_message(state.input_message)
        )
        if should_retry:
            return ForcedScriptFlowRetryNode()
        return End(result)


@dataclass
class ForcedScriptFlowRetryNode(BaseNode[ExpertScriptRunState, None, AgentRunResult]):
    async def run(
        self,
        ctx: GraphRunContext[ExpertScriptRunState],
    ) -> End[AgentRunResult]:
        state = ctx.state
        state.retry_attempted = True
        forced_prompt_override = _build_force_script_flow_prompt(
            state.system_prompt_override or state.agent.system_prompt,
        )
        state.result = await run_agent_with_tools(
            state.agent,
            state.tools,
            state.bindings,
            input_message=state.input_message,
            trace_id=state.trace_id,
            user=state.user,
            message_history=state.message_history,
            run_id=state.run_id,
            session_id=state.session_id,
            openai_api_key=state.openai_api_key,
            anthropic_api_key=state.anthropic_api_key,
            system_prompt_override=forced_prompt_override,
            extra_tools=state.extra_tools,
        )
        return End(state.result)


expert_script_runtime_graph = Graph(
    nodes=(InitialModelRunNode, ScriptFlowRetryDecisionNode, ForcedScriptFlowRetryNode),
    state_type=ExpertScriptRunState,
)


async def run_expert_script_runtime_graph(
    *,
    agent: Agent,
    tools: list[Tool],
    bindings: list[AgentToolBinding],
    input_message: str,
    trace_id: str,
    user: AuthContext,
    message_history: list[Any] | None = None,
    run_id: UUID | None = None,
    session_id: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    system_prompt_override: str | None = None,
    extra_tools: list[Any] | None = None,
) -> AgentRunResult:
    state = ExpertScriptRunState(
        agent=agent,
        tools=tools,
        bindings=bindings,
        input_message=input_message,
        trace_id=trace_id,
        user=user,
        message_history=message_history,
        run_id=run_id,
        session_id=session_id,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        system_prompt_override=system_prompt_override,
        extra_tools=extra_tools,
    )
    result = await expert_script_runtime_graph.run(InitialModelRunNode(), state=state)
    return result.output
