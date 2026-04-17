from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_or_404, require_scope
from app.db.models.agent import Agent
from app.db.models.binding import AgentToolBinding
from app.db.models.dialog_tag import DialogTag
from app.db.models.function_post_action import FunctionPostAction
from app.db.models.function_rule import FunctionRule
from app.db.models.rule_execution_log import RuleExecutionLog
from app.db.models.tool import Tool
from app.db.models.tool_parameter import ToolParameter
from app.db.models.tenant import Tenant
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.function_rule import (
    DialogTagRead,
    FunctionPostActionCreate,
    FunctionPostActionRead,
    FunctionPostActionUpdate,
    FunctionRuleCreate,
    FunctionRuleRead,
    FunctionRuleUpdate,
    RuleExecutionTrace,
    RuleKillSwitchResponse,
    RuleApprovalDecisionRequest,
    RuleApprovalRead,
    RuleTestRequest,
    RuleTestResponse,
    RuleActionExecutionTrace,
)
from app.services.audit import write_audit
from app.services.function_rule_tool_factory import create_tool_for_function_rule
from app.services.function_rules_runtime import run_rules_for_phase
from app.core.config import get_settings

router = APIRouter()


def _to_parameter_type(schema_type: Any) -> str:
    if schema_type == "number":
        return "number"
    if schema_type == "boolean":
        return "boolean"
    return "text"


def _extract_tool_args_schema(condition_config: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(condition_config, dict):
        return None
    raw_schema = condition_config.get("tool_args_schema")
    if raw_schema is None:
        return None
    if isinstance(raw_schema, str):
        raw_schema = raw_schema.strip()
        if not raw_schema:
            return None
        try:
            raw_schema = json.loads(raw_schema)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="condition_config.tool_args_schema must be valid JSON object",
            ) from exc
    if not isinstance(raw_schema, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="condition_config.tool_args_schema must be an object",
        )
    if raw_schema.get("type") != "object":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="condition_config.tool_args_schema.type must be 'object'",
        )
    properties = raw_schema.get("properties", {})
    if not isinstance(properties, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="condition_config.tool_args_schema.properties must be an object",
        )
    return raw_schema


async def _sync_internal_tool_schema(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    tool_id: UUID | None,
    condition_config: dict[str, Any] | None,
) -> None:
    schema = _extract_tool_args_schema(condition_config)
    if schema is None or tool_id is None:
        return
    tool = await get_or_404(
        db,
        Tool,
        id=tool_id,
        tenant_id=tenant_id,
        label="Tool",
        extra_where=[Tool.is_deleted.is_(False)],
    )
    if tool.execution_type != "internal":
        return

    tool.input_schema = schema
    existing_stmt = select(ToolParameter).where(
        ToolParameter.tool_id == tool.id,
        ToolParameter.tenant_id == tenant_id,
    )
    existing_params = (await db.execute(existing_stmt)).scalars().all()
    for item in existing_params:
        await db.delete(item)
    await db.flush()

    properties = schema.get("properties", {})
    required_set = set(schema.get("required", []) or [])
    for index, (name, prop) in enumerate(properties.items()):
        if not isinstance(name, str):
            continue
        prop_dict = prop if isinstance(prop, dict) else {}
        enum_values = prop_dict.get("enum")
        normalized_enum = [str(item) for item in enum_values] if isinstance(enum_values, list) else None
        db.add(
            ToolParameter(
                tenant_id=tenant_id,
                tool_id=tool.id,
                name=name,
                type=_to_parameter_type(prop_dict.get("type")),
                instruction=str(prop_dict.get("description") or f"Parameter '{name}'"),
                required=name in required_set,
                is_optional=name not in required_set,
                enum_values=normalized_enum,
                x_from_ai=bool(prop_dict.get("x-fromAI", True)),
                default_value=prop_dict.get("default"),
                order_index=index,
            )
        )


def _is_object_schema(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("type") != "object":
        return False
    properties = value.get("properties")
    return isinstance(properties, dict)


def _hydrated_condition_config(rule: FunctionRule) -> dict[str, Any]:
    cfg = dict(rule.condition_config or {})
    schema = cfg.get("tool_args_schema")
    if _is_object_schema(schema):
        return cfg
    if not rule.tool or rule.tool.execution_type != "internal":
        return cfg
    if _is_object_schema(rule.tool.input_schema):
        cfg["tool_args_schema"] = rule.tool.input_schema
    return cfg


def _to_rule_read(rule: FunctionRule) -> FunctionRuleRead:
    payload = FunctionRuleRead.model_validate(rule).model_dump()
    payload["condition_config"] = _hydrated_condition_config(rule)
    return FunctionRuleRead(**payload)


async def _ensure_agent(
    db: AsyncSession,
    *,
    agent_id: UUID,
    user: AuthContext,
) -> Agent:
    return await get_or_404(
        db,
        Agent,
        id=agent_id,
        tenant_id=user.tenant_id,
        label="Agent",
        extra_where=[Agent.is_deleted.is_(False)],
    )


async def _validate_webhook_action_config(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    action_type: str,
    action_config: dict[str, Any] | None,
) -> None:
    if action_type != "webhook":
        return
    cfg = action_config or {}
    tool_id = cfg.get("tool_id")
    if not tool_id:
        return
    try:
        tool_uuid = UUID(str(tool_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid webhook tool_id") from exc
    tool = await get_or_404(
        db,
        Tool,
        id=tool_uuid,
        tenant_id=tenant_id,
        label="Tool",
        extra_where=[Tool.is_deleted.is_(False)],
    )
    if tool.execution_type != "http_webhook" or not tool.endpoint or tool.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Webhook action requires active http_webhook tool with endpoint",
        )
    if tool.webhook_scope not in ("function_only", "both"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected webhook is not available for function actions",
        )


@router.get("/function-rules", response_model=list[FunctionRuleRead])
async def list_function_rules(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> list[FunctionRuleRead]:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    stmt = (
        select(FunctionRule)
        .options(selectinload(FunctionRule.actions), selectinload(FunctionRule.tool))
        .where(
            FunctionRule.tenant_id == user.tenant_id,
            FunctionRule.agent_id == agent_id,
        )
        .order_by(FunctionRule.priority.asc(), FunctionRule.created_at.asc())
    )
    rules = (await db.execute(stmt)).scalars().all()
    return [_to_rule_read(rule) for rule in rules]


@router.post("/function-rules", response_model=FunctionRuleRead, status_code=status.HTTP_201_CREATED)
async def create_function_rule(
    agent_id: UUID,
    payload: FunctionRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> FunctionRuleRead:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    resolved_tool_id = payload.tool_id
    if resolved_tool_id:
        await get_or_404(
            db,
            Tool,
            id=resolved_tool_id,
            tenant_id=user.tenant_id,
            label="Tool",
            extra_where=[Tool.is_deleted.is_(False)],
        )
        binding_stmt = select(AgentToolBinding.id).where(
            AgentToolBinding.tenant_id == user.tenant_id,
            AgentToolBinding.agent_id == agent_id,
            AgentToolBinding.tool_id == resolved_tool_id,
        )
        if (await db.execute(binding_stmt)).scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tool must be bound to this agent",
            )
    else:
        created_tool = await create_tool_for_function_rule(
            db,
            tenant_id=user.tenant_id,
            rule_name=payload.name,
            condition_config=payload.condition_config,
        )
        resolved_tool_id = created_tool.id

    rule = FunctionRule(
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        name=payload.name,
        enabled=payload.enabled,
        dry_run=payload.dry_run,
        stop_on_match=payload.stop_on_match,
        allow_semantic=payload.allow_semantic,
        priority=payload.priority,
        trigger_mode=payload.trigger_mode,
        condition_type=payload.condition_type,
        condition_config=payload.condition_config,
        tool_id=resolved_tool_id,
        reaction_to_execution=payload.reaction_to_execution,
        behavior_after_execution=payload.behavior_after_execution,
    )
    db.add(rule)
    await db.flush()

    for action in payload.actions:
        db.add(
            FunctionPostAction(
                tenant_id=user.tenant_id,
                rule_id=rule.id,
                action_type=action.action_type,
                action_config=action.action_config,
                on_status=action.on_status,
                order_index=action.order_index,
                enabled=action.enabled,
            )
        )
    await _sync_internal_tool_schema(
        db,
        tenant_id=user.tenant_id,
        tool_id=resolved_tool_id,
        condition_config=payload.condition_config,
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Function rule name already exists") from exc
    await db.refresh(rule)
    await write_audit(db, user, "function_rule.create", "function_rule", str(rule.id))

    stmt = (
        select(FunctionRule)
        .options(selectinload(FunctionRule.actions), selectinload(FunctionRule.tool))
        .where(FunctionRule.id == rule.id)
    )
    saved = (await db.execute(stmt)).scalar_one()
    return _to_rule_read(saved)


@router.get("/function-rules/{rule_id}", response_model=FunctionRuleRead)
async def get_function_rule(
    agent_id: UUID,
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> FunctionRuleRead:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    stmt = (
        select(FunctionRule)
        .options(selectinload(FunctionRule.actions), selectinload(FunctionRule.tool))
        .where(
            FunctionRule.id == rule_id,
            FunctionRule.agent_id == agent_id,
            FunctionRule.tenant_id == user.tenant_id,
        )
    )
    rule = (await db.execute(stmt)).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Function rule not found")
    return _to_rule_read(rule)


@router.put("/function-rules/{rule_id}", response_model=FunctionRuleRead)
async def update_function_rule(
    agent_id: UUID,
    rule_id: UUID,
    payload: FunctionRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> FunctionRuleRead:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    rule = await get_or_404(
        db,
        FunctionRule,
        id=rule_id,
        tenant_id=user.tenant_id,
        label="Function rule",
        extra_where=[FunctionRule.agent_id == agent_id],
    )

    # Exclude actions from dump: model_dump() turns nested models into dicts, which
    # breaks action_payload.action_type below (AttributeError → 500).
    update_data = payload.model_dump(exclude_unset=True, exclude={"actions"})
    actions_field_set = "actions" in payload.model_fields_set

    if "tool_id" in update_data and update_data["tool_id"] is not None:
        await get_or_404(
            db,
            Tool,
            id=update_data["tool_id"],
            tenant_id=user.tenant_id,
            label="Tool",
            extra_where=[Tool.is_deleted.is_(False)],
        )
        binding_stmt = select(AgentToolBinding.id).where(
            AgentToolBinding.tenant_id == user.tenant_id,
            AgentToolBinding.agent_id == agent_id,
            AgentToolBinding.tool_id == update_data["tool_id"],
        )
        if (await db.execute(binding_stmt)).scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tool must be bound to this agent",
            )
    for key, value in update_data.items():
        setattr(rule, key, value)

    if actions_field_set:
        to_persist = list(payload.actions or [])
        for action_payload in to_persist:
            await _validate_webhook_action_config(
                db,
                tenant_id=user.tenant_id,
                action_type=action_payload.action_type,
                action_config=action_payload.action_config,
            )
        await db.execute(
            delete(FunctionPostAction).where(FunctionPostAction.rule_id == rule.id)
        )
        await db.flush()
        for action in to_persist:
            db.add(
                FunctionPostAction(
                    tenant_id=user.tenant_id,
                    rule_id=rule.id,
                    action_type=action.action_type,
                    action_config=action.action_config,
                    on_status=action.on_status,
                    order_index=action.order_index,
                    enabled=action.enabled,
                )
            )

    target_condition_config = update_data.get("condition_config", rule.condition_config)
    target_tool_id = update_data.get("tool_id", rule.tool_id)
    await _sync_internal_tool_schema(
        db,
        tenant_id=user.tenant_id,
        tool_id=target_tool_id,
        condition_config=target_condition_config,
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Function rule name already exists") from exc
    await db.refresh(rule)
    await write_audit(db, user, "function_rule.update", "function_rule", str(rule.id))

    stmt = (
        select(FunctionRule)
        .options(selectinload(FunctionRule.actions), selectinload(FunctionRule.tool))
        .where(FunctionRule.id == rule.id)
    )
    saved = (await db.execute(stmt)).scalar_one()
    return _to_rule_read(saved)


@router.delete("/function-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_function_rule(
    agent_id: UUID,
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    rule = await get_or_404(
        db,
        FunctionRule,
        id=rule_id,
        tenant_id=user.tenant_id,
        label="Function rule",
        extra_where=[FunctionRule.agent_id == agent_id],
    )
    linked_tool_id = rule.tool_id
    deleted_binding_id: UUID | None = None
    deleted_tool_id: UUID | None = None

    await db.delete(rule)
    await db.flush()

    # Cleanup orphan internal tool generated for this function rule:
    # if no other rules reference it, remove agent binding and soft-delete the tool.
    if linked_tool_id is not None:
        other_rule_stmt = (
            select(FunctionRule.id)
            .where(
                FunctionRule.tenant_id == user.tenant_id,
                FunctionRule.tool_id == linked_tool_id,
            )
            .limit(1)
        )
        has_other_rules = (await db.execute(other_rule_stmt)).scalar_one_or_none()
        if has_other_rules is None:
            tool_stmt = select(Tool).where(
                Tool.id == linked_tool_id,
                Tool.tenant_id == user.tenant_id,
                Tool.is_deleted.is_(False),
            )
            tool = (await db.execute(tool_stmt)).scalar_one_or_none()
            if tool is not None and tool.execution_type == "internal":
                binding_stmt = select(AgentToolBinding).where(
                    AgentToolBinding.tenant_id == user.tenant_id,
                    AgentToolBinding.agent_id == agent_id,
                    AgentToolBinding.tool_id == linked_tool_id,
                )
                binding = (await db.execute(binding_stmt)).scalar_one_or_none()
                if binding is not None:
                    deleted_binding_id = binding.id
                    await db.delete(binding)
                    await db.flush()

                remaining_binding_stmt = (
                    select(AgentToolBinding.id)
                    .where(
                        AgentToolBinding.tenant_id == user.tenant_id,
                        AgentToolBinding.tool_id == linked_tool_id,
                    )
                    .limit(1)
                )
                has_remaining_bindings = (await db.execute(remaining_binding_stmt)).scalar_one_or_none()
                if has_remaining_bindings is None:
                    tool.is_deleted = True
                    tool.deleted_at = datetime.utcnow()
                    deleted_tool_id = tool.id

    await db.commit()
    await write_audit(db, user, "function_rule.delete", "function_rule", str(rule.id))
    if deleted_binding_id is not None:
        await write_audit(db, user, "binding.delete", "binding", str(deleted_binding_id))
    if deleted_tool_id is not None:
        await write_audit(db, user, "tool.delete", "tool", str(deleted_tool_id))


@router.post("/function-rules/{rule_id}/actions", response_model=FunctionPostActionRead, status_code=status.HTTP_201_CREATED)
async def create_rule_action(
    agent_id: UUID,
    rule_id: UUID,
    payload: FunctionPostActionCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> FunctionPostActionRead:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    await get_or_404(
        db,
        FunctionRule,
        id=rule_id,
        tenant_id=user.tenant_id,
        label="Function rule",
        extra_where=[FunctionRule.agent_id == agent_id],
    )

    await _validate_webhook_action_config(
        db,
        tenant_id=user.tenant_id,
        action_type=payload.action_type,
        action_config=payload.action_config,
    )

    action = FunctionPostAction(
        tenant_id=user.tenant_id,
        rule_id=rule_id,
        action_type=payload.action_type,
        action_config=payload.action_config,
        on_status=payload.on_status,
        order_index=payload.order_index,
        enabled=payload.enabled,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    await write_audit(db, user, "function_rule_action.create", "function_post_action", str(action.id))
    return FunctionPostActionRead.model_validate(action)


@router.put("/function-rules/{rule_id}/actions/{action_id}", response_model=FunctionPostActionRead)
async def update_rule_action(
    agent_id: UUID,
    rule_id: UUID,
    action_id: UUID,
    payload: FunctionPostActionUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> FunctionPostActionRead:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    await get_or_404(
        db,
        FunctionRule,
        id=rule_id,
        tenant_id=user.tenant_id,
        label="Function rule",
        extra_where=[FunctionRule.agent_id == agent_id],
    )
    action = await get_or_404(
        db,
        FunctionPostAction,
        id=action_id,
        tenant_id=user.tenant_id,
        label="Function action",
        extra_where=[FunctionPostAction.rule_id == rule_id],
    )
    update_data = payload.model_dump(exclude_unset=True)
    resolved_action_type = update_data.get("action_type", action.action_type)
    resolved_action_config = update_data.get("action_config", action.action_config)
    await _validate_webhook_action_config(
        db,
        tenant_id=user.tenant_id,
        action_type=resolved_action_type,
        action_config=resolved_action_config,
    )
    for key, value in update_data.items():
        setattr(action, key, value)
    await db.commit()
    await db.refresh(action)
    await write_audit(db, user, "function_rule_action.update", "function_post_action", str(action.id))
    return FunctionPostActionRead.model_validate(action)


@router.delete("/function-rules/{rule_id}/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule_action(
    agent_id: UUID,
    rule_id: UUID,
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    await get_or_404(
        db,
        FunctionRule,
        id=rule_id,
        tenant_id=user.tenant_id,
        label="Function rule",
        extra_where=[FunctionRule.agent_id == agent_id],
    )
    action = await get_or_404(
        db,
        FunctionPostAction,
        id=action_id,
        tenant_id=user.tenant_id,
        label="Function action",
        extra_where=[FunctionPostAction.rule_id == rule_id],
    )
    await db.delete(action)
    await db.commit()
    await write_audit(db, user, "function_rule_action.delete", "function_post_action", str(action.id))


@router.post("/function-rules/test", response_model=RuleTestResponse)
async def test_function_rules(
    agent_id: UUID,
    payload: RuleTestRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> RuleTestResponse:
    agent = await _ensure_agent(db, agent_id=agent_id, user=user)
    tenant = await db.get(Tenant, user.tenant_id)
    rules_enabled = bool(getattr(agent, "function_rules_enabled", True)) and bool(
        getattr(tenant, "function_rules_enabled", True)
    )
    semantic_allowed = bool(getattr(agent, "function_rules_allow_semantic", True)) and bool(
        getattr(tenant, "function_rules_allow_semantic", True)
    )
    trace_id = payload.trace_id or str(uuid4())
    traces, context = await run_rules_for_phase(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        session_id=payload.session_id,
        trace_id=trace_id,
        phase="pre_run",
        message=payload.message,
        user=user,
        run_id=None,
        context={"simulate_only": not payload.run_tool_calls},
        rules_enabled=rules_enabled,
        semantic_allowed=semantic_allowed,
    )
    replay_messages = [msg for msg in payload.historical_messages if msg.strip()]
    for replay_message in replay_messages:
        replay_traces, context = await run_rules_for_phase(
            db,
            tenant_id=user.tenant_id,
            agent_id=agent_id,
            session_id=payload.session_id,
            trace_id=trace_id,
            phase="pre_run",
            message=replay_message,
            user=user,
            run_id=None,
            context=context,
            rules_enabled=rules_enabled,
            semantic_allowed=semantic_allowed,
        )
        traces.extend(replay_traces)
    if not payload.run_tool_calls:
        await db.rollback()
    else:
        await db.commit()

    formatted = [
        RuleExecutionTrace(
            rule_id=trace.rule_id,
            matched=trace.matched,
            reason=trace.reason,
            score=trace.score,
            actions=[
                RuleActionExecutionTrace(
                    action_id=item.action_id,
                    action_type=item.action_type,
                    status=item.status,
                    details=item.details,
                )
                for item in trace.actions
            ],
        )
        for trace in traces
    ]
    tags_created = context.get("tags_created", [])
    should_pause = bool(context.get("should_pause", False))
    return RuleTestResponse(
        trace_id=trace_id,
        matched_rules=formatted,
        tags_created=tags_created,
        should_pause=should_pause,
    )


@router.get("/dialogs/{session_id}/tags", response_model=list[DialogTagRead])
async def list_dialog_tags(
    agent_id: UUID,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> list[DialogTagRead]:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    stmt = (
        select(DialogTag)
        .where(
            DialogTag.tenant_id == user.tenant_id,
            DialogTag.agent_id == agent_id,
            DialogTag.session_id == session_id,
        )
        .order_by(DialogTag.created_at.desc())
    )
    tags = (await db.execute(stmt)).scalars().all()
    return [DialogTagRead.model_validate(tag) for tag in tags]


@router.post("/function-rules/kill-switch", response_model=RuleKillSwitchResponse)
async def kill_switch_rules(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> RuleKillSwitchResponse:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    stmt = (
        update(FunctionRule)
        .where(
            FunctionRule.tenant_id == user.tenant_id,
            FunctionRule.agent_id == agent_id,
            FunctionRule.enabled.is_(True),
        )
        .values(enabled=False)
    )
    result = await db.execute(stmt)
    await db.commit()
    await write_audit(db, user, "function_rule.kill_switch", "agent", str(agent_id))
    disabled = result.rowcount or 0
    return RuleKillSwitchResponse(disabled_rules_count=disabled)


@router.get("/function-rules/approvals", response_model=list[RuleApprovalRead])
async def list_rule_approvals(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> list[RuleApprovalRead]:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    if not get_settings().function_rules_hitl_enabled:
        return []
    stmt = (
        select(RuleExecutionLog)
        .where(
            RuleExecutionLog.tenant_id == user.tenant_id,
            RuleExecutionLog.agent_id == agent_id,
            RuleExecutionLog.approval_status == "pending_approval",
        )
        .order_by(RuleExecutionLog.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        RuleApprovalRead(
            id=row.id,
            rule_id=row.rule_id,
            run_id=row.run_id,
            session_id=row.session_id,
            trace_id=row.trace_id,
            approval_status=row.approval_status,
            approval_metadata=row.approval_metadata,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/function-rules/approvals/{approval_id}/decision", response_model=RuleApprovalRead)
async def decide_rule_approval(
    agent_id: UUID,
    approval_id: UUID,
    payload: RuleApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> RuleApprovalRead:
    await _ensure_agent(db, agent_id=agent_id, user=user)
    if not get_settings().function_rules_hitl_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="HITL approvals are disabled by feature flag",
        )
    approval = await get_or_404(
        db,
        RuleExecutionLog,
        id=approval_id,
        tenant_id=user.tenant_id,
        label="Rule approval",
        extra_where=[RuleExecutionLog.agent_id == agent_id],
    )
    approval.approval_status = payload.decision
    approval.approval_metadata = payload.metadata
    await db.commit()
    await db.refresh(approval)
    await write_audit(db, user, "function_rule.approval_decision", "rule_execution_log", str(approval.id))
    return RuleApprovalRead(
        id=approval.id,
        rule_id=approval.rule_id,
        run_id=approval.run_id,
        session_id=approval.session_id,
        trace_id=approval.trace_id,
        approval_status=approval.approval_status,
        approval_metadata=approval.approval_metadata,
        created_at=approval.created_at,
    )
