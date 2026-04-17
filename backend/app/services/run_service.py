"""
Run service — бизнес-логика запуска агентов, сессий и token-usage.

Извлечено из routers/runs.py, чтобы убрать SQL и бизнес-логику из роутеров.
Используется в runs.py, webhooks.py, ws.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import HTTPException, status
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.agent import Agent
from app.db.models.binding import AgentToolBinding
from app.db.models.direct_question import DirectQuestion
from app.db.models.function_rule import FunctionRule
from app.db.models.agent_user_state import AgentUserState
from app.db.models.run import Run
from app.db.models.run_token_usage_step import RunTokenUsageStep
from app.db.models.session_message import SessionMessage
from app.db.models.tenant import Tenant
from app.db.models.tool import Tool
from app.db.models.tool_call_log import ToolCallLog
from app.schemas.auth import AuthContext
from app.services.runtime import (
    AgentRunResult,
    messages_adapter,
    run_agent_with_tools,
    serialize_assistant_text_for_session,
)
from app.services.runtime.context_assembler import (
    normalize_augment_prompt_blocks,
    select_optional_runtime_tool_categories,
)
from app.services.runtime.tool_registry import build_optional_runtime_tools
from app.services.runtime.scenario_runtime import apply_dialog_scenario_phases_before_llm
from app.core.config import get_settings
from app.services.logfire_cost_reconcile import schedule_logfire_cost_reconcile
from app.services.agent_user_state import is_agent_user_disabled_by_session, normalize_identity
from app.services.direct_questions import schedule_direct_question_followup
from app.services.direct_questions.safety import sanitize_direct_question_content, split_direct_question_content
from app.services.runtime.model_resolver import provider_prefix_from_model_name
from app.services.tenant_llm_config import get_decrypted_api_key
from app.services.function_rules_runtime import run_rules_for_phase
from app.services.tenant_balance import sync_run_balance_charge
from app.services.token_costing import apply_fallback_costs
from app.services.tool_executor import ToolExecutionError
from app.utils.broadcast import broadcaster
from app.utils.message_mapping import extract_text_contents

logger = structlog.get_logger(__name__)


# Backward-compatible aliases for existing tests/imports.
_normalize_augment_prompt_blocks = normalize_augment_prompt_blocks
_select_optional_runtime_tool_categories = select_optional_runtime_tool_categories


def _session_messages_contain_output_text(
    messages: list[dict[str, Any]],
    output_text: str,
) -> bool:
    """Проверка, что финальный текст ответа уже представлен в сообщениях для session_messages."""
    needle = output_text.strip()
    if not needle:
        return True
    for m in messages:
        if not isinstance(m, dict):
            continue
        for txt in extract_text_contents(m):
            if txt.strip() == needle:
                return True
    return False


def _agent_disabled_http_error(agent_id: UUID | Any) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "agent_disabled",
            "message": "Агент временно отключён. Входящие сообщения продолжают сохраняться.",
            "agent_id": str(agent_id),
        },
    )


def _agent_user_disabled_http_error(agent_id: UUID | Any, session_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "agent_user_disabled",
            "message": "Агент отключён для этого пользователя. Входящие сообщения продолжают сохраняться.",
            "agent_id": str(agent_id),
            "session_id": session_id,
        },
    )


def _build_tool_display_text(name: str, when_to_call: str, args: dict[str, Any]) -> str:
    lines = [f"🔧 {name}", f"Когда вызывать: {json.dumps(when_to_call, ensure_ascii=False)}"]
    if args:
        for key, value in args.items():
            lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
    else:
        lines.append("(без параметров)")
    return "\n".join(lines)


def _extract_forced_reaction_output(tools_called: list[dict[str, Any]] | None) -> str | None:
    if not tools_called:
        return None
    messages: list[str] = []
    for call in tools_called:
        if not isinstance(call, dict):
            continue
        # Guardrail: apply forced post-tool reactions only for tool calls
        # emitted in the current run to avoid history-driven output overrides.
        if call.get("source") != "new_messages":
            continue
        raw = call.get("post_tool_reaction_messages")
        if not isinstance(raw, list):
            continue
        for item in raw:
            text = str(item).strip()
            if text:
                messages.append(text)
    if not messages:
        return None
    return "\n".join(messages)


def _extract_tool_events_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    from app.utils.message_mapping import extract_structured_parts

    events: list[dict[str, Any]] = []
    for part in extract_structured_parts(message):
        kind = part.get("kind")
        if kind == "tool-call":
            events.append(
                {
                    "type": "tool_call",
                    "tool_name": part.get("tool_name"),
                    "tool_call_id": part.get("tool_call_id"),
                    "args": part.get("args") if isinstance(part.get("args"), dict) else {},
                    "result": None,
                }
            )
        elif kind == "tool-return":
            events.append(
                {
                    "type": "tool_result",
                    "tool_name": part.get("tool_name"),
                    "tool_call_id": part.get("tool_call_id"),
                    "args": part.get("args") if isinstance(part.get("args"), dict) else None,
                    "result": part.get("result"),
                }
            )
    return events


def _to_json_object(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"items": value}
    if isinstance(value, (str, int, float, bool)):
        return {"value": value}
    return {"value": str(value)}


async def _build_direct_question_tool_meta(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    tools_called: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    if not tools_called:
        return None

    for call in tools_called:
        if not isinstance(call, dict):
            continue
        if call.get("name") != "get_direct_answer":
            continue

        raw_args = call.get("args")
        if not isinstance(raw_args, dict):
            continue

        direct_question_id = raw_args.get("direct_question_id")
        if not direct_question_id:
            continue

        try:
            question_uuid = UUID(str(direct_question_id))
        except (ValueError, TypeError):
            continue

        # db.get() использует identity map SQLAlchemy — если объект уже загружен
        # в этой сессии (например, через build_direct_answer_tool), повторного
        # SELECT не будет.
        question = await db.get(DirectQuestion, question_uuid)
        if question is None or question.tenant_id != tenant_id or question.agent_id != agent_id:
            continue

        safe_content = sanitize_direct_question_content(question.content)
        system_instruction, user_content = split_direct_question_content(safe_content)

        return {
            "source": "direct_question_tool_call",
            "question_id": str(question.id),
            "title": question.title,
            "content": user_content,
            "system_instruction": system_instruction,
            "interrupt_dialog": question.interrupt_dialog,
            "notify_telegram": question.notify_telegram,
            "followup": question.followup if isinstance(question.followup, dict) else None,
        }
    return None


async def _disable_agent_user_for_session(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    session_id: str,
    changed_by_user_id: UUID,
) -> bool:
    """
    Disable agent only for the current dialog identity (platform:user).

    Returns True when session identity is valid and state was upserted.
    """
    if not session_id or ":" not in session_id:
        return False
    platform, platform_user_id = session_id.split(":", 1)
    if not platform or not platform_user_id:
        return False

    norm_platform, norm_user_id = normalize_identity(platform, platform_user_id)
    stmt = select(AgentUserState).where(
        AgentUserState.tenant_id == tenant_id,
        AgentUserState.agent_id == agent_id,
        AgentUserState.platform == norm_platform,
        AgentUserState.platform_user_id == norm_user_id,
    )
    state = (await db.execute(stmt)).scalar_one_or_none()
    if state is None:
        state = AgentUserState(
            tenant_id=tenant_id,
            agent_id=agent_id,
            platform=norm_platform,
            platform_user_id=norm_user_id,
        )
        db.add(state)

    state.is_disabled = True
    state.disabled_at = datetime.now(timezone.utc)
    state.disabled_by_user_id = changed_by_user_id
    return True


# ---------------------------------------------------------------------------
# Load agent & tools
# ---------------------------------------------------------------------------

async def load_agent_and_tools(
    db: AsyncSession,
    agent_id: UUID,
    tenant_id: UUID,
    *,
    allow_disabled: bool = False,
) -> tuple[Agent, list[Tool], list[AgentToolBinding]]:
    """Загрузить агента, его tool-bindings и активные tools."""
    agent_stmt = select(Agent).where(
        Agent.id == agent_id,
        Agent.tenant_id == tenant_id,
        Agent.is_deleted.is_(False),
    )
    agent = (await db.execute(agent_stmt)).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if agent.is_disabled and not allow_disabled:
        raise _agent_disabled_http_error(agent.id)

    logger.info(
        "agent_loaded_from_db",
        agent_id=str(agent.id),
        system_prompt_preview=agent.system_prompt[:50] if agent.system_prompt else "",
    )

    bindings_stmt = (
        select(AgentToolBinding)
        .options(selectinload(AgentToolBinding.credential))
        .where(
            AgentToolBinding.agent_id == agent_id,
            AgentToolBinding.tenant_id == tenant_id,
        )
    )
    bindings = (await db.execute(bindings_stmt)).scalars().all()
    tool_ids = [binding.tool_id for binding in bindings]
    if not tool_ids:
        return agent, [], bindings

    tools_stmt = select(Tool).where(
        Tool.id.in_(tool_ids),
        Tool.tenant_id == tenant_id,
        Tool.is_deleted.is_(False),
        Tool.status == "active",
        or_(Tool.webhook_scope.in_(["tool", "both"]), Tool.webhook_scope.is_(None)),
        or_(
            Tool.execution_type != "internal",
            exists(
                select(FunctionRule.id).where(
                    FunctionRule.tenant_id == tenant_id,
                    FunctionRule.agent_id == agent_id,
                    FunctionRule.tool_id == Tool.id,
                )
            ),
        ),
    )
    tools = (await db.execute(tools_stmt)).scalars().all()
    return agent, tools, bindings


# ---------------------------------------------------------------------------
# Session history
# ---------------------------------------------------------------------------

def _is_manager_message(msg: Any) -> bool:
    """Проверить, является ли сообщение менеджерским (не распознаётся pydantic-ai)."""
    if not isinstance(msg, dict):
        return False
    if msg.get("role") == "manager":
        return True
    parts = msg.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict):
                pk = part.get("part_kind") or part.get("partKind")
                if pk in ("manager-message", "manager_message", "manager"):
                    return True
    return False


async def get_session_history(
    db: AsyncSession,
    session_id: str,
    tenant_id: UUID,
    agent_id: UUID,
    limit: int = 10,
) -> list[Any] | None:
    """Получить историю сообщений для конкретного агента и сессии.

    Фильтрация по agent_id необходима для изоляции агентов.
    """
    if limit <= 0:
        return None

    stmt = (
        select(SessionMessage.message)
        .join(Run, SessionMessage.run_id == Run.id)
        .where(
            SessionMessage.session_id == session_id,
            SessionMessage.tenant_id == tenant_id,
            Run.agent_id == agent_id,
        )
        .order_by(SessionMessage.message_index.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    logger.info(
        "get_session_history_debug",
        session_id=session_id,
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        limit=limit,
        raw_messages_count=len(messages),
        raw_preview=[str(m)[:200] for m in messages[:3]] if messages else [],
    )

    if not messages:
        return None

    messages.reverse()

    filtered = [m for m in messages if not _is_manager_message(m)]
    if not filtered:
        return None

    return messages_adapter.validate_python(filtered)


# ---------------------------------------------------------------------------
# Append session messages
# ---------------------------------------------------------------------------

async def append_session_messages(
    db: AsyncSession,
    tenant_id: UUID,
    session_id: str,
    run_id: UUID,
    new_messages: list[dict[str, Any]],
    max_history: int | None,
    agent_id: UUID | None = None,
    user_info: dict[str, Any] | None = None,
) -> None:
    """Сохранить новые сообщения сессии в БД и опубликовать в broadcast."""
    if not new_messages:
        return

    stmt = select(func.max(SessionMessage.message_index)).where(
        SessionMessage.session_id == session_id,
        SessionMessage.tenant_id == tenant_id,
    )
    last_index = (await db.execute(stmt)).scalar_one_or_none() or 0
    next_index = last_index

    if user_info is None:
        effective_user_info: dict[str, Any] = {"session_id": session_id}
        if session_id.startswith("telegram:"):
            effective_user_info.update(
                {
                    "platform": "telegram",
                    "platform_id": session_id.split(":", 1)[1],
                    "integration_channel_type": "telegram",
                    "integration_channel_label": "Telegram бот",
                }
            )
        elif session_id.startswith("telegram_phone:"):
            effective_user_info.update(
                {
                    "platform": "telegram_phone",
                    "platform_id": session_id.split(":", 1)[1],
                    "integration_channel_type": "telegram_phone",
                    "integration_channel_label": "Telegram номер",
                }
            )
        elif session_id.startswith("max:"):
            effective_user_info.update(
                {
                    "platform": "max",
                    "platform_id": session_id.split(":", 1)[1],
                    "integration_channel_type": "max",
                    "integration_channel_label": "MAX",
                }
            )
        elif session_id.startswith("whatsapp:"):
            effective_user_info.update(
                {
                    "platform": "whatsapp",
                    "platform_id": session_id.split(":", 1)[1],
                    "integration_channel_type": "whatsapp",
                    "integration_channel_label": "WhatsApp",
                }
            )
    else:
        effective_user_info = {**user_info, "session_id": session_id}

    entries: list[SessionMessage] = []
    for payload in new_messages:
        next_index += 1
        msg_with_info = {**payload, "user_info": effective_user_info}
        entries.append(
            SessionMessage(
                tenant_id=tenant_id,
                session_id=session_id,
                run_id=run_id,
                message_index=next_index,
                message=msg_with_info,
            )
        )

    db.add_all(entries)
    await db.flush()

    # Публикуем новые сообщения в шину для Real-time интерфейса менеджера
    if agent_id:
        is_new_dialog = last_index == 0

        for entry in entries:
            message_id = str(entry.id) if entry.id is not None else str(uuid4())
            created_at = datetime.utcnow().isoformat()
            event_data = {
                "id": message_id,
                "session_id": session_id,
                "agent_id": str(agent_id),
                "message": entry.message,
                "created_at": created_at,
            }
            await broadcaster.publish(agent_id, {"type": "message_created", "data": event_data})
            for tool_event in _extract_tool_events_from_message(entry.message):
                await broadcaster.publish(
                    agent_id,
                    {
                        "type": tool_event["type"],
                        "data": {
                            "message_id": message_id,
                            "session_id": session_id,
                            "agent_id": str(agent_id),
                            "created_at": created_at,
                            "tool_name": tool_event.get("tool_name"),
                            "tool_call_id": tool_event.get("tool_call_id"),
                            "args": tool_event.get("args"),
                            "result": tool_event.get("result"),
                        },
                    },
                )

        last_msg_text = ""
        if new_messages:
            last_msg = new_messages[-1]
            parts = last_msg.get("parts", [])
            for part in parts:
                if part.get("part_kind") in ["user-prompt", "text"]:
                    last_msg_text = part.get("content", "")
                    break

        dialog_event = {
            "id": session_id,
            "agent_id": str(agent_id),
            "title": last_msg_text[:50] + "..." if len(last_msg_text) > 50 else (last_msg_text or "Новый диалог"),
            "last_message_preview": last_msg_text[:100],
            "last_message_at": datetime.utcnow().isoformat(),
            "is_new": is_new_dialog,
        }
        await broadcaster.publish(agent_id, {"type": "dialog_updated", "data": dialog_event})

    if max_history and max_history > 0:
        prune_subquery = (
            select(SessionMessage.id)
            .where(
                SessionMessage.session_id == session_id,
                SessionMessage.tenant_id == tenant_id,
            )
            .order_by(SessionMessage.message_index.desc())
            .offset(max_history)
        )
        prune_stmt = delete(SessionMessage).where(SessionMessage.id.in_(prune_subquery.scalar_subquery()))
        await db.execute(prune_stmt)


# ---------------------------------------------------------------------------
# Append token usage steps
# ---------------------------------------------------------------------------

def append_token_usage_steps(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    run_id: UUID,
    session_id: str,
    token_usage_steps: list[dict[str, Any]] | None,
) -> None:
    """Создать записи RunTokenUsageStep для данного run."""
    if not token_usage_steps:
        return

    entries: list[RunTokenUsageStep] = []
    for idx, step in enumerate(token_usage_steps, start=1):
        if not isinstance(step, dict):
            continue
        step_index = step.get("step_index") or idx
        entries.append(
            RunTokenUsageStep(
                tenant_id=tenant_id,
                agent_id=agent_id,
                run_id=run_id,
                session_id=session_id,
                model_name=step.get("model_name"),
                step_index=int(step_index),
                prompt_tokens=step.get("prompt_tokens"),
                completion_tokens=step.get("completion_tokens"),
                total_tokens=step.get("total_tokens"),
                input_cached_tokens=step.get("input_cached_tokens"),
                input_non_cached_tokens=step.get("input_non_cached_tokens"),
                cache_read_tokens=step.get("cache_read_tokens"),
                cache_write_tokens=step.get("cache_write_tokens"),
                reasoning_tokens=step.get("reasoning_tokens"),
                audio_tokens=step.get("audio_tokens"),
                input_audio_tokens=step.get("input_audio_tokens"),
                output_audio_tokens=step.get("output_audio_tokens"),
                cache_audio_read_tokens=step.get("cache_audio_read_tokens"),
                accepted_prediction_tokens=step.get("accepted_prediction_tokens"),
                rejected_prediction_tokens=step.get("rejected_prediction_tokens"),
                cost_usd=step.get("cost_usd"),
                cost_rub=step.get("cost_rub"),
                cost_usd_logfire=step.get("cost_usd_logfire"),
            )
        )

    if entries:
        db.add_all(entries)


# ---------------------------------------------------------------------------
# Execute run (common logic for create_run, stream_run, webhooks, ws)
# ---------------------------------------------------------------------------

async def execute_agent_run(
    db: AsyncSession,
    *,
    agent: Agent,
    tools: list[Tool],
    bindings: list[AgentToolBinding],
    run: Run,
    input_message: str,
    trace_id: str,
    user: AuthContext,
    session_id: str,
    message_history: list[Any] | None = None,
    new_messages_filter: Any | None = None,
    user_info: dict[str, Any] | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    skip_dialog_scenario_phases: bool = False,
    system_prompt_override: str | None = None,
) -> AgentRunResult:
    """Запустить агента, обновить Run, сохранить сообщения и token-usage.

    Parameters
    ----------
    new_messages_filter : callable, optional
        Если указан, результат new_messages будет пропущен через эту функцию
        перед сохранением в сессию (используется в webhooks для filter_user_prompts).
    user_info : dict, optional
        Информация о пользователе для broadcast (например, данные Telegram).
    skip_dialog_scenario_phases : bool
        Если True — не выполнять фазы dialog_start / client_message / client_return
        (их уже выполнил process_webhook_inbound_agent_message перед этим вызовом).

    Returns
    -------
    AgentRunResult
        Результат выполнения агента.

    Raises
    ------
    ToolExecutionError
        Ошибка выполнения инструмента — run помечается как failed.
    Exception
        Любая другая ошибка — run помечается как failed.
    """
    if agent.is_disabled:
        raise _agent_disabled_http_error(agent.id)
    if await is_agent_user_disabled_by_session(
        db,
        tenant_id=run.tenant_id,
        agent_id=agent.id,
        session_id=session_id,
    ):
        raise _agent_user_disabled_http_error(agent.id, session_id)

    settings = get_settings()
    selected_optional_categories, optional_tool_meta = _select_optional_runtime_tool_categories(
        input_message,
        mode=settings.runtime_optional_tools_mode,
    )
    logger.info(
        "runtime_optional_tool_selection",
        agent_id=str(agent.id),
        session_id=session_id,
        trace_id=trace_id,
        **optional_tool_meta,
    )

    direct_question_meta: dict[str, Any] | None = None
    # system_prompt_override may be passed in from webhook (pre-computed augment_prompt);
    # dialog-phase scenario augmentation below may further extend it.
    extra_runtime_tools = []
    retrieval_decisions: list[dict[str, Any]] = []

    if openai_api_key is None:
        openai_api_key = await get_decrypted_api_key(db, run.tenant_id, "openai")
    if anthropic_api_key is None:
        anthropic_api_key = await get_decrypted_api_key(db, run.tenant_id, "anthropic")

    effective_model = agent.model or settings.pydanticai_default_model
    if effective_model == "string":
        effective_model = settings.pydanticai_default_model
    chat_provider = provider_prefix_from_model_name(effective_model) or "openai"
    if chat_provider == "anthropic" and not anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "API-ключ Anthropic не настроен для организации. "
                "Установите его в Настройках организации → Ключи LLM."
            ),
        )

    optional_tools_bundle = await build_optional_runtime_tools(
        db=db,
        agent=agent,
        tenant_id=run.tenant_id,
        session_id=session_id,
        selected_categories=selected_optional_categories,
        settings=settings,
        openai_api_key=openai_api_key,
    )
    extra_runtime_tools = optional_tools_bundle.tools
    retrieval_decisions = optional_tools_bundle.retrieval_decisions

    # Merge expertise bridge into system_prompt_override when expert scripts are active.
    if optional_tools_bundle.system_prompt_addition:
        base = (system_prompt_override or agent.system_prompt or "").rstrip()
        system_prompt_override = base + optional_tools_bundle.system_prompt_addition

    # Same phases as inbound webhooks (webhooks_inbound_agent): dialog_start on first message
    # in session, then client_message / client_return. Test chat (/runs, WS) previously skipped
    # these and only ran agent_message after the model — so «Начало диалога» did not fire in UI.
    scenario_short_circuit = False
    result: AgentRunResult | None = None
    if not skip_dialog_scenario_phases:
        pre_llm = await apply_dialog_scenario_phases_before_llm(
            db,
            agent=agent,
            run=run,
            input_message=input_message,
            trace_id=trace_id,
            user=user,
            session_id=session_id,
            user_info=user_info,
            system_prompt_override=system_prompt_override,
            settings=settings,
        )
        system_prompt_override = pre_llm.system_prompt_override
        scenario_short_circuit = pre_llm.scenario_short_circuit
        result = pre_llm.short_circuit_result
        # NOTE: silent_reaction is intentionally NOT a short-circuit here.
        # For pre-LLM phases (dialog_start / client_message) it means "no extra
        # scenario message", but the LLM must still run — especially when
        # augment_prompt has been populated above and needs to reach the model.

    if result is None:
        result = await run_agent_with_tools(
            agent,
            tools,
            bindings,
            input_message=input_message,
            trace_id=trace_id,
            user=user,
            message_history=message_history,
            run_id=run.id,
            session_id=session_id,
            openai_api_key=openai_api_key,
            anthropic_api_key=anthropic_api_key,
            system_prompt_override=system_prompt_override,
            extra_tools=extra_runtime_tools or None,
        )

    try:
        tenant_row = await db.get(Tenant, run.tenant_id)
        rules_enabled = bool(getattr(agent, "function_rules_enabled", True)) and bool(
            getattr(tenant_row, "function_rules_enabled", True) if tenant_row else True
        )
        semantic_allowed = bool(getattr(agent, "function_rules_allow_semantic", True)) and bool(
            getattr(tenant_row, "function_rules_allow_semantic", True) if tenant_row else True
        )
        if rules_enabled and not scenario_short_circuit:
            ui = user_info if isinstance(user_info, dict) else {}
            await run_rules_for_phase(
                db,
                tenant_id=run.tenant_id,
                agent_id=agent.id,
                session_id=session_id,
                trace_id=trace_id,
                phase="agent_message",
                message=str(result.output or ""),
                user=user,
                run_id=run.id,
                context={
                    "user_info": ui,
                    "agent_timezone": getattr(agent, "timezone", None) or "UTC",
                    "input_message": input_message,
                    "message": input_message,
                    "assistant_output": str(result.output or ""),
                },
                rules_enabled=True,
                semantic_allowed=semantic_allowed,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "agent_message_scenario_rules_failed",
            agent_id=str(agent.id),
            session_id=session_id,
            error=str(exc),
        )

    # Enrich tool calls with metadata useful for UI/debug:
    # - when_to_call: tool description
    # - parameter_schema: original input schema properties
    if result.tools_called:
        tools_by_name = {tool.name: tool for tool in tools}
        enriched_tools_called: list[dict[str, Any]] = []
        for item in result.tools_called:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str):
                enriched_tools_called.append(item)
                continue

            tool_row = tools_by_name.get(name)
            if not tool_row:
                enriched_tools_called.append(item)
                continue

            enriched_item = dict(item)
            when_to_call = tool_row.description or ""
            enriched_item.setdefault("when_to_call", when_to_call)
            enriched_item.setdefault("description", when_to_call)
            if isinstance(tool_row.input_schema, dict):
                enriched_item.setdefault("parameter_schema", tool_row.input_schema.get("properties", {}))
            args = enriched_item.get("args")
            if not isinstance(args, dict):
                args = {}
            enriched_item.setdefault(
                "parameters_display",
                [f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in args.items()],
            )
            enriched_item.setdefault(
                "display_text",
                _build_tool_display_text(name=name, when_to_call=when_to_call, args=args),
            )
            enriched_tools_called.append(enriched_item)
        result.tools_called = enriched_tools_called

    if not direct_question_meta:
        direct_question_meta = await _build_direct_question_tool_meta(
            db,
            tenant_id=run.tenant_id,
            agent_id=agent.id,
            tools_called=result.tools_called,
        )
    if direct_question_meta:
        should_interrupt_dialog = bool(direct_question_meta.get("interrupt_dialog"))
        if should_interrupt_dialog:
            disabled = await _disable_agent_user_for_session(
                db,
                tenant_id=run.tenant_id,
                agent_id=agent.id,
                session_id=session_id,
                changed_by_user_id=user.user_id,
            )
            direct_question_meta["agent_user_disabled"] = disabled
            if disabled:
                logger.info(
                    "direct_question_interrupt_applied",
                    agent_id=str(agent.id),
                    session_id=session_id,
                    question_id=direct_question_meta.get("question_id"),
                )
        question_id_raw = direct_question_meta.get("question_id")
        followup_payload = direct_question_meta.get("followup")
        if isinstance(question_id_raw, str):
            try:
                scheduled = await schedule_direct_question_followup(
                    db,
                    tenant_id=run.tenant_id,
                    agent_id=agent.id,
                    direct_question_id=UUID(question_id_raw),
                    run_id=run.id,
                    session_id=session_id,
                    followup=followup_payload if isinstance(followup_payload, dict) else None,
                    max_attempts=settings.direct_questions_followup_max_attempts,
                )
                if scheduled:
                    direct_question_meta["followup_scheduled"] = True
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "direct_question_followup_schedule_failed",
                    agent_id=str(agent.id),
                    run_id=str(run.id),
                    session_id=session_id,
                    question_id=question_id_raw,
                    error=str(exc),
                )
        result.orchestration_meta = direct_question_meta

    forced_reaction_output = _extract_forced_reaction_output(result.tools_called)
    direct_question_content: str | None = None
    if direct_question_meta and isinstance(direct_question_meta, dict):
        raw_content = direct_question_meta.get("content")
        if isinstance(raw_content, str) and raw_content.strip():
            direct_question_content = raw_content.strip()

    if forced_reaction_output:
        result.output = forced_reaction_output
    elif direct_question_content:
        model_output = str(result.output or "").strip()
        # Keep system-prompt style and composition from model;
        # fallback to managed direct content only when model returned nothing.
        if not model_output:
            result.output = direct_question_content

    cost_usd, cost_rub = await apply_fallback_costs(db, token_usage_steps=result.token_usage_steps)

    run.status = "succeeded"
    run.output_message = result.output
    run.messages = result.new_messages
    run.prompt_tokens = result.prompt_tokens
    run.completion_tokens = result.completion_tokens
    run.total_tokens = result.total_tokens
    run.cost_usd = cost_usd
    run.cost_rub = cost_rub
    run.logfire_reconcile_status = "pending"
    run.logfire_reconcile_error = None
    run.tools_called = list(result.tools_called)
    if retrieval_decisions:
        run.knowledge_retrieval_decisions = retrieval_decisions

    # Build tool_call_logs for all tools invoked in this run.
    # DB-backed tools are captured via result.tool_call_events (has timing + payloads).
    # Virtual/runtime tools (get_direct_answer, search_knowledge_files, etc.) only appear
    # in result.tools_called and are synthesised here as basic log entries.
    tools_by_name = {tool.name: tool for tool in tools}
    tool_meta_by_name: dict[str, dict[str, Any]] = {}
    for item in result.tools_called:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str):
                tool_meta_by_name[name] = item

    logs: list[ToolCallLog] = []
    captured_names: set[str] = set()

    for raw_event in result.tool_call_events:
        if not isinstance(raw_event, dict):
            continue
        tool_name = str(raw_event.get("tool_name") or "").strip()
        if not tool_name:
            continue
        captured_names.add(tool_name)

        tool_row = tools_by_name.get(tool_name)
        meta = tool_meta_by_name.get(tool_name, {})
        tool_id = tool_row.id if tool_row is not None else None
        if tool_id is None and isinstance(raw_event.get("tool_id"), str):
            try:
                tool_id = UUID(raw_event["tool_id"])
            except (TypeError, ValueError):
                tool_id = None

        status_value = str(raw_event.get("status") or "error").lower()
        normalized_status = "success" if status_value == "success" else "error"
        invoked_at = raw_event.get("invoked_at")
        if not isinstance(invoked_at, datetime):
            invoked_at = datetime.now(timezone.utc)
        duration_ms_raw = raw_event.get("duration_ms")
        duration_ms = int(duration_ms_raw) if isinstance(duration_ms_raw, int) else None
        if duration_ms is not None and duration_ms < 0:
            duration_ms = 0

        tool_description = str(
            meta.get("description")
            or meta.get("when_to_call")
            or (tool_row.description if tool_row is not None else "")
            or tool_name
        )
        tool_settings_url = (
            f"/agents/{agent.id}/tools/{tool_id}" if tool_id else f"/agents/{agent.id}"
        )

        logs.append(
            ToolCallLog(
                tenant_id=run.tenant_id,
                run_id=run.id,
                agent_id=agent.id,
                tool_id=tool_id,
                tool_name=tool_name,
                tool_description=tool_description,
                tool_settings_url=tool_settings_url,
                status=normalized_status,
                invoked_at=invoked_at,
                duration_ms=duration_ms,
                user_info=_to_json_object(user_info),
                request_payload=_to_json_object(raw_event.get("request_payload")),
                response_payload=_to_json_object(raw_event.get("response_payload")),
                error_payload=_to_json_object(raw_event.get("error_payload")),
            )
        )

    # Fallback: capture virtual/runtime tools not tracked via tool_call_events
    for item in result.tools_called:
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("name") or "").strip()
        if not tool_name or tool_name in captured_names:
            continue
        args = item.get("args") or {}
        tool_description = str(
            item.get("description") or item.get("when_to_call") or tool_name
        )
        logs.append(
            ToolCallLog(
                tenant_id=run.tenant_id,
                run_id=run.id,
                agent_id=agent.id,
                tool_id=None,
                tool_name=tool_name,
                tool_description=tool_description,
                tool_settings_url=f"/agents/{agent.id}",
                status="success",
                invoked_at=datetime.now(timezone.utc),
                duration_ms=None,
                user_info=_to_json_object(user_info),
                request_payload=_to_json_object(args) if args else None,
                response_payload=_to_json_object(item.get("result")),
                error_payload=None,
            )
        )

    if logs:
        db.add_all(logs)
        await db.flush()

    await sync_run_balance_charge(db, run=run)

    messages_to_save: list[dict[str, Any]] = list(result.new_messages or [])
    if new_messages_filter and messages_to_save:
        messages_to_save = new_messages_filter(messages_to_save)

    # Финальный ответ пользователю иногда не попадает в new_messages (или не сериализуется в текст).
    # Без этой записи в диалогах остаются только входящие сообщения.
    out_text = (result.output or "").strip()
    if out_text and not _session_messages_contain_output_text(messages_to_save, out_text):
        messages_to_save = [
            *messages_to_save,
            serialize_assistant_text_for_session(out_text),
        ]

    await append_session_messages(
        db,
        run.tenant_id,
        session_id,
        run.id,
        messages_to_save,
        agent.max_history_messages,
        agent_id=agent.id,
        user_info=user_info,
    )
    append_token_usage_steps(
        db,
        tenant_id=run.tenant_id,
        agent_id=agent.id,
        run_id=run.id,
        session_id=session_id,
        token_usage_steps=result.token_usage_steps,
    )

    return result
