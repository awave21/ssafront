from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.run import Run
from app.db.models.session_message import SessionMessage
from app.db.models.tenant import Tenant
from app.schemas.auth import AuthContext
from app.services.dialog_state import get_last_user_message_at
from app.services.function_rules_runtime import merge_scenario_rule_contexts, run_rules_for_phase
from app.services.runtime import AgentRunResult
from app.services.runtime.context_assembler import build_system_prompt_override

logger = structlog.get_logger(__name__)


def _days_since_last_user_message(last_at: datetime | None) -> float | None:
    if last_at is None:
        return None
    at = last_at
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - at).total_seconds() / 86400.0


async def merge_dialog_scenario_rule_phases(
    db: AsyncSession,
    *,
    tenant_id: Any,
    agent_id: Any,
    session_id: str,
    trace_id: str,
    run_id: Any,
    input_message: str,
    user: AuthContext,
    user_info: dict[str, Any] | None,
    agent_timezone: str,
    rules_enabled: bool,
    semantic_allowed: bool,
    rules_failure_event: str,
) -> dict[str, Any]:
    merged_scenario_ctx: dict[str, Any] = {}
    if not rules_enabled:
        return merged_scenario_ctx

    count_stmt = select(func.count(SessionMessage.id)).where(
        SessionMessage.session_id == session_id,
        SessionMessage.tenant_id == tenant_id,
    )
    prior_message_count = int((await db.execute(count_stmt)).scalar_one() or 0)
    last_user_at = await get_last_user_message_at(db, agent_id=agent_id, session_id=session_id)
    days_since = _days_since_last_user_message(last_user_at)
    ui_pre = user_info if isinstance(user_info, dict) else {}
    base_ctx: dict[str, Any] = {
        "user_info": ui_pre,
        "agent_timezone": agent_timezone,
        "input_message": input_message,
        "message": input_message,
        "days_since_last_user_message": days_since,
    }

    phases: list[str] = []
    if prior_message_count == 0:
        phases.append("dialog_start")
    phases.extend(["client_message", "client_return"])
    for phase in phases:
        try:
            _, ctx_part = await run_rules_for_phase(
                db,
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=session_id,
                trace_id=trace_id,
                phase=phase,
                message=input_message,
                user=user,
                run_id=run_id,
                context=base_ctx,
                rules_enabled=True,
                semantic_allowed=semantic_allowed,
            )
            merged_scenario_ctx = merge_scenario_rule_contexts(merged_scenario_ctx, ctx_part)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                rules_failure_event,
                phase=phase,
                agent_id=str(agent_id),
                session_id=session_id,
                error=str(exc),
            )

    return merged_scenario_ctx


@dataclass
class DialogScenarioPreLLMResult:
    merged_scenario_ctx: dict[str, Any]
    system_prompt_override: str | None
    scenario_short_circuit: bool
    short_circuit_result: AgentRunResult | None


async def apply_dialog_scenario_phases_before_llm(
    db: AsyncSession,
    *,
    agent: Agent,
    run: Run,
    input_message: str,
    trace_id: str,
    user: AuthContext,
    session_id: str,
    user_info: dict[str, Any] | None,
    system_prompt_override: str | None,
    settings: Any,
) -> DialogScenarioPreLLMResult:
    """
    Pre-LLM phases: dialog_start (first message), client_message, client_return.

    Mirrors execute_agent_run behavior: merges scenario ctx, applies augment_prompt caps,
    may short-circuit on messages_to_send / forced_result.
    """
    merged_scenario_ctx: dict[str, Any] = {}
    scenario_short_circuit = False
    short_circuit_result: AgentRunResult | None = None

    tenant_pre = await db.get(Tenant, run.tenant_id)
    rules_enabled_pre = bool(getattr(agent, "function_rules_enabled", True)) and bool(
        getattr(tenant_pre, "function_rules_enabled", True) if tenant_pre else True
    )
    semantic_allowed_pre = bool(getattr(agent, "function_rules_allow_semantic", True)) and bool(
        getattr(tenant_pre, "function_rules_allow_semantic", True) if tenant_pre else True
    )
    if rules_enabled_pre:
        merged_scenario_ctx = await merge_dialog_scenario_rule_phases(
            db,
            tenant_id=run.tenant_id,
            agent_id=agent.id,
            session_id=session_id,
            trace_id=trace_id,
            run_id=run.id,
            input_message=input_message,
            user=user,
            user_info=user_info,
            agent_timezone=getattr(agent, "timezone", None) or "UTC",
            rules_enabled=True,
            semantic_allowed=semantic_allowed_pre,
            rules_failure_event="execute_agent_run_scenario_rules_failed",
        )

    prompt_assembly = build_system_prompt_override(
        agent.system_prompt,
        merged_scenario_ctx,
        max_blocks=settings.runtime_augment_prompt_max_blocks,
        max_chars=settings.runtime_augment_prompt_max_chars,
    )
    if prompt_assembly.meta and (
        prompt_assembly.meta.get("input_count") != prompt_assembly.meta.get("kept_count")
        or prompt_assembly.meta.get("truncated_last_block")
    ):
        logger.info(
            "scenario_augment_prompt_normalized",
            agent_id=str(agent.id),
            session_id=session_id,
            trace_id=trace_id,
            **prompt_assembly.meta,
        )

    out_override = system_prompt_override
    if prompt_assembly.system_prompt_override:
        out_override = prompt_assembly.system_prompt_override

    # Непустой список с пустыми строками (например шаблон send_message дал "")
    # не должен обрывать цепочку: иначе ответ клиенту будет пустым без вызова LLM.
    msgs = merged_scenario_ctx.get("messages_to_send")
    first_reply = ""
    if isinstance(msgs, list):
        for item in msgs:
            text = str(item).strip()
            if text:
                first_reply = text
                break
    if first_reply:
        short_circuit_result = AgentRunResult(output=first_reply)
        scenario_short_circuit = True
    else:
        forced_raw = merged_scenario_ctx.get("forced_result")
        if isinstance(forced_raw, str) and forced_raw.strip():
            short_circuit_result = AgentRunResult(output=forced_raw.strip())
            scenario_short_circuit = True

    return DialogScenarioPreLLMResult(
        merged_scenario_ctx=merged_scenario_ctx,
        system_prompt_override=out_override,
        scenario_short_circuit=scenario_short_circuit,
        short_circuit_result=short_circuit_result,
    )
