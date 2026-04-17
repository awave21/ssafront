"""Общая логика: входящее текстовое сообщение → сессия + опционально execute_agent_run."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.user_messages import MESSENGER_AGENT_FAILURE_USER_MESSAGE
from app.db.models.agent import Agent
from app.db.models.run import Run
from app.db.models.tenant import Tenant
from app.schemas.auth import AuthContext
from app.services.dialog_state import (
    set_dialog_status,
    update_last_user_message_at,
)
from app.services.function_rules_runtime import run_rules_for_phase
from app.services.tool_executor import ToolExecutionError
from app.utils.broadcast import broadcaster
from app.utils.message_mapping import build_user_prompt, filter_user_prompts

logger = structlog.get_logger(__name__)


async def _disable_messenger_dialog_after_agent_failure(
    db: AsyncSession,
    agent: Agent,
    *,
    session_id: str,
) -> None:
    """Отключить автоответы агента для этой сессии и уведомить CRM (broadcast)."""
    try:
        await set_dialog_status(
            db,
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            session_id=session_id,
            new_status="disabled",
        )
    except Exception as exc:
        logger.warning(
            "messenger_disable_dialog_failed",
            agent_id=str(agent.id),
            session_id=session_id,
            error=str(exc),
        )
        return
    try:
        await broadcaster.publish(
            agent.id,
            {
                "type": "dialog_updated",
                "data": {
                    "id": session_id,
                    "session_id": session_id,
                    "agent_id": str(agent.id),
                    "status": "disabled",
                },
            },
        )
    except Exception as exc:
        logger.warning(
            "messenger_dialog_disabled_broadcast_failed",
            agent_id=str(agent.id),
            session_id=session_id,
            error=str(exc),
        )


async def append_wappi_linked_account_message(
    db: AsyncSession,
    agent: Agent,
    *,
    session_id: str,
    text: str,
    base_user_info: dict[str, Any],
    log_source: str = "wappi_operator",
    message_metadata: dict[str, Any] | None = None,
) -> None:
    """
    Сохранить в диалог текст, отправленный вручную с привязанного номера (Wappi: from_me и т.п.).
    Роль — как у менеджера: пауза агента и отличие от клиента в UI.
    """
    from uuid import uuid4

    from app.services.dialog_state import update_last_manager_message
    from app.services.run_service import append_session_messages
    from app.utils.message_mapping import build_manager_message

    trace_id = str(uuid4())
    run = Run(
        tenant_id=agent.tenant_id,
        agent_id=agent.id,
        session_id=session_id,
        status="succeeded",
        input_message=text,
        trace_id=trace_id,
        output_message=None,
        messages=[],
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_usd=None,
        cost_rub=None,
        logfire_reconcile_status="skipped",
        logfire_reconcile_error="wappi_linked_account_message",
        tools_called=[],
    )
    db.add(run)
    await db.flush()

    operator_info = {
        **base_user_info,
        "session_id": session_id,
        "platform": "manager",
        "manager_source": "wappi_linked_messenger",
    }

    manager_message = build_manager_message(text)
    if message_metadata:
        manager_message.update(message_metadata)

    await append_session_messages(
        db,
        agent.tenant_id,
        session_id,
        run.id,
        [manager_message],
        agent.max_history_messages,
        agent_id=agent.id,
        user_info=operator_info,
    )
    run.updated_at = datetime.utcnow()

    tenant = await db.get(Tenant, agent.tenant_id)
    rules_enabled = bool(getattr(agent, "function_rules_enabled", True)) and bool(
        getattr(tenant, "function_rules_enabled", True) if tenant else True
    )
    semantic_allowed = bool(getattr(agent, "function_rules_allow_semantic", True)) and bool(
        getattr(tenant, "function_rules_allow_semantic", True) if tenant else True
    )
    if rules_enabled:
        webhook_user = AuthContext(
            user_id=agent.owner_user_id,
            tenant_id=agent.tenant_id,
            scopes=["tools:write"],
        )
        try:
            await run_rules_for_phase(
                db,
                tenant_id=agent.tenant_id,
                agent_id=agent.id,
                session_id=session_id,
                trace_id=trace_id,
                phase="manager_message",
                message=text,
                user=webhook_user,
                run_id=run.id,
                context={
                    "user_info": operator_info,
                    "agent_timezone": getattr(agent, "timezone", None) or "UTC",
                    "input_message": text,
                    "message": text,
                },
                rules_enabled=True,
                semantic_allowed=semantic_allowed,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "manager_message_scenario_rules_failed",
                agent_id=str(agent.id),
                session_id=session_id,
                error=str(exc),
            )

    await update_last_manager_message(db, agent_id=agent.id, tenant_id=agent.tenant_id, session_id=session_id)


async def process_webhook_inbound_agent_message(
    db: AsyncSession,
    agent: Agent,
    *,
    session_id: str,
    input_text: str,
    user_info: dict[str, Any],
    run_agent: bool = True,
    log_source: str = "webhook",
    telegram_debug_audit: bool = False,
) -> str | None:
    """
    Сохранить сообщение пользователя в сессию; при run_agent=True выполнить агента.
    Возвращает текст ответа агента или None (в т.ч. при run_agent=False).
    """
    from app.core.config import get_settings
    from app.services.logfire_cost_reconcile import schedule_logfire_cost_reconcile
    from app.services.runtime.context_assembler import build_system_prompt_override
    from app.services.runtime.scenario_runtime import merge_dialog_scenario_rule_phases
    from app.services.run_service import (
        append_session_messages,
        execute_agent_run,
        get_session_history,
        load_agent_and_tools,
    )

    effective_user_info = {**user_info, "session_id": session_id}

    webhook_user = AuthContext(
        user_id=agent.owner_user_id,
        tenant_id=agent.tenant_id,
        scopes=["tools:write"],
    )

    if telegram_debug_audit:
        try:
            os.makedirs("/opt/app-agent/myapp/backend/.cursor", exist_ok=True)
            with open("/opt/app-agent/myapp/backend/.cursor/debug-e26c68.log", "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "e26c68",
                            "runId": "audit-1",
                            "hypothesisId": "H4",
                            "location": "webhooks_inbound_agent:process_webhook_inbound_agent_message",
                            "message": "telegram_webhook_auth_context",
                            "data": {
                                "agent_id": str(agent.id),
                                "tenant_id": str(agent.tenant_id),
                                "session_id": session_id,
                                "scopes": list(webhook_user.scopes),
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass

    trace_id = str(uuid4())
    run = Run(
        tenant_id=agent.tenant_id,
        agent_id=agent.id,
        session_id=session_id,
        status="running",
        input_message=input_text,
        trace_id=trace_id,
    )
    db.add(run)
    await db.flush()

    try:
        user_message = build_user_prompt(input_text)

        tenant = await db.get(Tenant, agent.tenant_id)
        rules_enabled = bool(getattr(agent, "function_rules_enabled", True)) and bool(
            getattr(tenant, "function_rules_enabled", True) if tenant else True
        )
        semantic_allowed = bool(getattr(agent, "function_rules_allow_semantic", True)) and bool(
            getattr(tenant, "function_rules_allow_semantic", True) if tenant else True
        )

        merged_ctx: dict[str, Any] = {}
        if rules_enabled and run_agent:
            merged_ctx = await merge_dialog_scenario_rule_phases(
                db,
                tenant_id=agent.tenant_id,
                agent_id=agent.id,
                session_id=session_id,
                trace_id=trace_id,
                run_id=run.id,
                input_message=input_text,
                user=webhook_user,
                user_info=effective_user_info,
                agent_timezone=getattr(agent, "timezone", None) or "UTC",
                rules_enabled=True,
                semantic_allowed=semantic_allowed,
                rules_failure_event="inbound_scenario_rules_failed",
            )

        await append_session_messages(
            db,
            agent.tenant_id,
            session_id,
            run.id,
            [user_message],
            agent.max_history_messages,
            agent_id=agent.id,
            user_info=effective_user_info,
        )
        await update_last_user_message_at(
            db,
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            session_id=session_id,
            commit=False,
        )
        await db.commit()

        if not run_agent:
            run.status = "succeeded"
            run.output_message = None
            run.messages = []
            run.prompt_tokens = 0
            run.completion_tokens = 0
            run.total_tokens = 0
            run.cost_usd = None
            run.cost_rub = None
            run.logfire_reconcile_status = "skipped"
            run.logfire_reconcile_error = "run_not_executed"
            run.tools_called = []
            return None

        if merged_ctx.get("messages_to_send"):
            first_reply = str(merged_ctx["messages_to_send"][0]).strip()
            run.status = "succeeded"
            run.output_message = first_reply
            run.messages = []
            run.prompt_tokens = 0
            run.completion_tokens = 0
            run.total_tokens = 0
            run.cost_usd = None
            run.cost_rub = None
            run.logfire_reconcile_status = "skipped"
            run.logfire_reconcile_error = "scenario_forced_message"
            run.tools_called = []
            return first_reply

        # silent_reaction is NOT a short-circuit when augment_prompt is also set:
        # the instruction must reach the LLM. Only skip the LLM when silent AND no
        # augmented prompt is present (i.e. the scenario truly wants a silent response).
        if merged_ctx.get("silent_reaction") and not merged_ctx.get("augment_prompt"):
            run.status = "succeeded"
            run.output_message = None
            run.messages = []
            run.prompt_tokens = 0
            run.completion_tokens = 0
            run.total_tokens = 0
            run.cost_usd = None
            run.cost_rub = None
            run.logfire_reconcile_status = "skipped"
            run.logfire_reconcile_error = "scenario_silent"
            run.tools_called = []
            return None

        forced = merged_ctx.get("forced_result")
        if isinstance(forced, str) and forced.strip():
            run.status = "succeeded"
            run.output_message = forced.strip()
            run.messages = []
            run.prompt_tokens = 0
            run.completion_tokens = 0
            run.total_tokens = 0
            run.cost_usd = None
            run.cost_rub = None
            run.logfire_reconcile_status = "skipped"
            run.logfire_reconcile_error = "scenario_forced_result"
            run.tools_called = []
            return forced.strip()

        agent_obj, tools, bindings = await load_agent_and_tools(db, agent.id, agent.tenant_id)
        message_history = await get_session_history(
            db, session_id, agent.tenant_id, agent.id, limit=agent.max_history_messages
        )

        settings = get_settings()
        prompt_assembly = build_system_prompt_override(
            agent_obj.system_prompt,
            merged_ctx,
            max_blocks=settings.runtime_augment_prompt_max_blocks,
            max_chars=settings.runtime_augment_prompt_max_chars,
        )
        if prompt_assembly.meta and (
            prompt_assembly.meta.get("input_count") != prompt_assembly.meta.get("kept_count")
            or prompt_assembly.meta.get("truncated_last_block")
        ):
            logger.info(
                "webhook_augment_prompt_normalized",
                agent_id=str(agent.id),
                session_id=session_id,
                trace_id=trace_id,
                **prompt_assembly.meta,
            )
        webhook_system_prompt_override = prompt_assembly.system_prompt_override

        result = await execute_agent_run(
            db,
            agent=agent_obj,
            tools=tools,
            bindings=bindings,
            run=run,
            input_message=input_text,
            trace_id=trace_id,
            user=webhook_user,
            session_id=session_id,
            message_history=message_history,
            new_messages_filter=filter_user_prompts,
            user_info=effective_user_info,
            skip_dialog_scenario_phases=True,
            system_prompt_override=webhook_system_prompt_override,
        )
        schedule_logfire_cost_reconcile(run_id=run.id, trace_id=trace_id)
        return result.output
    except ToolExecutionError as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.logfire_reconcile_status = "skipped"
        run.logfire_reconcile_error = "run_failed"
        await _disable_messenger_dialog_after_agent_failure(db, agent, session_id=session_id)
        return MESSENGER_AGENT_FAILURE_USER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "webhook_inbound_agent_failed",
            trace_id=trace_id,
            log_source=log_source,
            error=str(exc),
        )
        run.status = "failed"
        run.error_message = f"Runtime error: {str(exc)}"
        run.logfire_reconcile_status = "skipped"
        run.logfire_reconcile_error = "run_failed"
        await _disable_messenger_dialog_after_agent_failure(db, agent, session_id=session_id)
        return MESSENGER_AGENT_FAILURE_USER_MESSAGE
    finally:
        run.updated_at = datetime.utcnow()
        await db.commit()
