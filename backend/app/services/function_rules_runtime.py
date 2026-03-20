from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.dialog_tag import DialogTag
from app.db.models.function_post_action import FunctionPostAction
from app.db.models.function_rule import FunctionRule
from app.db.models.rule_execution_log import RuleExecutionLog
from app.db.models.tool import Tool
from app.schemas.auth import AuthContext
from app.core.config import get_settings
from app.services.agent_user_state import upsert_agent_user_state
from app.services.dialog_state import set_dialog_status
from app.services.semantic_matcher import semantic_match_text
from app.services.tool_executor import _ensure_allowed_domain, execute_tool_call
from app.utils.idempotency import generate_idempotency_key

logger = structlog.get_logger(__name__)


def _extract_session_identity(session_id: str) -> tuple[str, str] | None:
    if not session_id or ":" not in session_id:
        return None
    platform, platform_user_id = session_id.split(":", 1)
    platform = platform.strip().lower()
    platform_user_id = platform_user_id.strip()
    if not platform or not platform_user_id:
        return None
    return platform, platform_user_id


async def _pause_dialog_and_user(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    session_id: str,
    user: AuthContext,
) -> None:
    await set_dialog_status(
        db,
        agent_id=agent_id,
        tenant_id=tenant_id,
        session_id=session_id,
        new_status="paused",
    )

    identity = _extract_session_identity(session_id)
    if identity is None:
        return
    platform, platform_user_id = identity
    await upsert_agent_user_state(
        db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        platform=platform,
        platform_user_id=platform_user_id,
        is_disabled=True,
        changed_by_user_id=user.user_id,
    )


@dataclass
class ConditionResult:
    matched: bool
    score: float | None = None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    action_id: UUID | None
    action_type: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleRuntimeResult:
    rule_id: UUID
    matched: bool
    score: float | None
    reason: str | None
    actions: list[ActionResult] = field(default_factory=list)


def _truncate_for_trace(value: Any, *, max_str: int = 500, max_items: int = 20, max_depth: int = 4) -> Any:
    if max_depth <= 0:
        return "<truncated>"
    if isinstance(value, str):
        if len(value) <= max_str:
            return value
        return f"{value[:max_str]}...<truncated {len(value) - max_str} chars>"
    if isinstance(value, list):
        trimmed = [_truncate_for_trace(item, max_str=max_str, max_items=max_items, max_depth=max_depth - 1) for item in value[:max_items]]
        if len(value) > max_items:
            trimmed.append(f"<truncated {len(value) - max_items} items>")
        return trimmed
    if isinstance(value, dict):
        items = list(value.items())
        trimmed_items = items[:max_items]
        output: dict[str, Any] = {
            str(key): _truncate_for_trace(item, max_str=max_str, max_items=max_items, max_depth=max_depth - 1)
            for key, item in trimmed_items
        }
        if len(items) > max_items:
            output["__truncated_keys__"] = len(items) - max_items
        return output
    return value


def _render_template(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        pattern = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")
        matches = list(pattern.finditer(value))
        if not matches:
            return value

        def _resolve_path(source: Any, path: list[str]) -> Any | None:
            current = source
            for key in path:
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    return None
            return current

        def _deep_find_key(source: Any, key: str, *, max_depth: int = 8) -> Any | None:
            if max_depth < 0:
                return None
            if isinstance(source, dict):
                if key in source:
                    return source.get(key)
                for value in source.values():
                    found = _deep_find_key(value, key, max_depth=max_depth - 1)
                    if found is not None:
                        return found
                return None
            if isinstance(source, list):
                for item in source:
                    found = _deep_find_key(item, key, max_depth=max_depth - 1)
                    if found is not None:
                        return found
                return None
            return None

        def _resolve_expr(expr: str) -> Any | None:
            token = expr.strip()
            if not token:
                return None

            if token in context:
                return context[token]

            if "." in token:
                root, *tail = token.split(".")
                if root in context:
                    return _resolve_path(context[root], tail)

            # Backward compatibility: allow {{field}} to be resolved
            # from tool payload contexts if the key is not top-level.
            for source_key in ("tool_result", "last_tool_result", "tool_args", "tool_call_args"):
                source = context.get(source_key)
                if not isinstance(source, dict):
                    continue
                if token in source:
                    return source.get(token)
                for nested_key in ("args", "result", "data", "payload"):
                    nested = source.get(nested_key)
                    if isinstance(nested, dict) and token in nested:
                        return nested.get(token)
                found = _deep_find_key(source, token)
                if found is not None:
                    return found
            return None

        if len(matches) == 1 and matches[0].span() == (0, len(value)):
            resolved = _resolve_expr(matches[0].group(1))
            return "" if resolved is None else resolved

        output = value
        for match in matches:
            resolved = _resolve_expr(match.group(1))
            replacement = "" if resolved is None else str(resolved)
            output = output.replace(match.group(0), replacement)
        return output
    if isinstance(value, list):
        return [_render_template(item, context) for item in value]
    if isinstance(value, dict):
        return {k: _render_template(v, context) for k, v in value.items()}
    return value


def _extract_latest_tool_call_args(
    context: dict[str, Any],
    *,
    preferred_tool_name: str | None = None,
) -> dict[str, Any]:
    tool_calls = context.get("tool_calls")
    if not isinstance(tool_calls, list):
        return {}

    preferred = preferred_tool_name.strip() if isinstance(preferred_tool_name, str) else None
    for item in reversed(tool_calls):
        if not isinstance(item, dict):
            continue
        if preferred:
            name = item.get("name")
            if not isinstance(name, str) or name.strip() != preferred:
                continue
        args = item.get("args")
        if isinstance(args, dict):
            return args
    return {}


def evaluate_condition(rule: FunctionRule, *, message: str, context: dict[str, Any]) -> ConditionResult:
    cfg = rule.condition_config or {}
    if rule.condition_type == "always":
        return ConditionResult(matched=True, reason="condition_type=always")

    if rule.condition_type == "keyword":
        keywords = [str(item) for item in cfg.get("keywords", []) if str(item).strip()]
        if not keywords:
            return ConditionResult(matched=False, reason="no keywords configured")
        text = message if cfg.get("case_sensitive") else message.lower()
        normalized_keywords = keywords if cfg.get("case_sensitive") else [item.lower() for item in keywords]
        match_mode = str(cfg.get("match", "any"))
        if match_mode == "all":
            matched = all(item in text for item in normalized_keywords)
        else:
            matched = any(item in text for item in normalized_keywords)
        return ConditionResult(
            matched=matched,
            score=1.0 if matched else 0.0,
            reason=f"keyword_{match_mode}",
            details={"keywords": keywords},
        )

    if rule.condition_type == "regex":
        patterns = [str(item) for item in cfg.get("patterns", []) if str(item).strip()]
        flags = re.IGNORECASE if not cfg.get("case_sensitive", False) else 0
        for pattern in patterns:
            if re.search(pattern, message, flags=flags):
                return ConditionResult(
                    matched=True,
                    score=1.0,
                    reason=f"regex matched: {pattern}",
                    details={"pattern": pattern},
                )
        return ConditionResult(matched=False, score=0.0, reason="regex not matched")

    if rule.condition_type == "json_context":
        field_name = str(cfg.get("field", "")).strip()
        equals = cfg.get("equals")
        contains = cfg.get("contains")
        if not field_name:
            return ConditionResult(matched=False, reason="json_context missing field")
        value = context.get(field_name)
        if equals is not None:
            matched = value == equals
            return ConditionResult(matched=matched, score=1.0 if matched else 0.0, reason=f"context equals {field_name}")
        if contains is not None:
            matched = contains in str(value or "")
            return ConditionResult(matched=matched, score=1.0 if matched else 0.0, reason=f"context contains {field_name}")
        return ConditionResult(matched=False, reason="json_context missing operator")

    if rule.condition_type == "semantic":
        threshold = float(cfg.get("semantic_threshold", 0.6))
        result = semantic_match_text(
            message,
            intents=cfg.get("intents"),
            examples=cfg.get("examples"),
            threshold=threshold,
        )
        details: dict[str, Any] = {"threshold": threshold}
        if result.intent:
            details["intent"] = result.intent
        return ConditionResult(
            matched=result.matched and rule.allow_semantic,
            score=result.score,
            reason=result.reason,
            details=details,
        )

    return ConditionResult(matched=False, reason=f"unsupported condition_type={rule.condition_type}")


async def _execute_rule_tool(
    db: AsyncSession,
    *,
    rule: FunctionRule,
    context: dict[str, Any],
    trace_id: str,
    user: AuthContext,
) -> tuple[dict[str, Any] | str | None, ActionResult | None]:
    if not rule.tool_id:
        return None, None
    tool = await db.get(Tool, rule.tool_id)
    if not tool or tool.is_deleted or tool.status != "active":
        return None, ActionResult(
            None,
            "rule_tool",
            "skipped",
            {"reason": "tool_not_available", "tool_id": str(rule.tool_id)},
        )

    raw_args = rule.condition_config.get("tool_args", {})
    args = _render_template(raw_args, context) if isinstance(raw_args, dict) else {}
    if tool.execution_type == "internal":
        result_payload: dict[str, Any] | str = {
            "mode": "internal",
            "tool_name": tool.name,
            "args": args,
            "status": "ok",
        }
    elif tool.execution_type == "http_webhook" and tool.endpoint:
        # region agent log
        try:
            os.makedirs("/opt/app-agent/myapp/backend/.cursor", exist_ok=True)
            with open("/opt/app-agent/myapp/backend/.cursor/debug-e26c68.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "e26c68",
                    "runId": "audit-1",
                    "hypothesisId": "H3",
                    "location": "app/services/function_rules_runtime.py:_execute_rule_tool",
                    "message": "rule_tool_execute_webhook",
                    "data": {
                        "rule_id": str(rule.id),
                        "tool_id": str(tool.id),
                        "execution_type": tool.execution_type,
                        "endpoint_host": urlparse(tool.endpoint).hostname if tool.endpoint else None,
                        "allowed_domains": None,
                        "secrets_ref": None,
                    },
                    "timestamp": int(time.time() * 1000),
                }) + "\n")
        except Exception:
            pass
        # endregion agent log
        result_payload = await execute_tool_call(
            endpoint=tool.endpoint,
            input_schema=tool.input_schema,
            args=args,
            trace_id=trace_id,
            auth_type=tool.auth_type,
            http_method=tool.http_method or "POST",
            parameter_mapping=tool.parameter_mapping,
            custom_headers=tool.custom_headers,
            secrets_ref=None,
            secret_payload=None,
            allowed_domains=None,
            timeout_ms=None,
            user=user,
        )
    else:
        return None, ActionResult(
            None,
            "rule_tool",
            "skipped",
            {"reason": "unsupported_tool_execution_type", "tool_id": str(tool.id), "execution_type": tool.execution_type},
        )
    return (
        result_payload,
        ActionResult(
            None,
            "rule_tool",
            "success",
            {
                "tool_id": str(tool.id),
                "tool_name": tool.name,
                "execution_type": tool.execution_type,
                "method": (tool.http_method or "POST").upper() if tool.execution_type == "http_webhook" else None,
                "host": urlparse(tool.endpoint).hostname if tool.endpoint else None,
                "endpoint": tool.endpoint,
                "args": _truncate_for_trace(args),
                "request_args": _truncate_for_trace(args),
                "response": _truncate_for_trace(result_payload),
            },
        ),
    )


async def execute_post_actions(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    session_id: str,
    trace_id: str,
    user: AuthContext,
    actions: list[FunctionPostAction],
    execution_status: str,
    context: dict[str, Any],
) -> tuple[list[ActionResult], dict[str, Any]]:
    settings = get_settings()
    results: list[ActionResult] = []
    output_context = dict(context)

    ordered_actions = sorted(actions, key=lambda item: item.order_index)
    max_actions = int(output_context.get("max_actions_per_rule") or settings.function_rule_max_actions)
    for action in ordered_actions:
        if len(results) >= max_actions:
            results.append(
                ActionResult(
                    None,
                    "guardrail",
                    "skipped",
                    {"reason": "max_actions_reached", "max_actions": max_actions},
                )
            )
            break
        if not action.enabled:
            continue
        if action.on_status not in (execution_status, "always"):
            continue
        cfg = action.action_config or {}
        started_at = time.monotonic()
        try:
            if action.action_type == "noop":
                results.append(ActionResult(action.id, action.action_type, "success"))
                continue

            if action.action_type == "set_tag":
                tag = str(cfg.get("tag", "")).strip()
                if tag:
                    db.add(
                        DialogTag(
                            tenant_id=tenant_id,
                            agent_id=agent_id,
                            session_id=session_id,
                            tag=tag,
                            source="rule_action",
                            confidence=cfg.get("confidence"),
                            tag_metadata={"trace_id": trace_id},
                        )
                    )
                    output_context.setdefault("tags_created", []).append(tag)
                results.append(ActionResult(action.id, action.action_type, "success", {"tag": tag}))
                continue

            if action.action_type == "pause_dialog":
                await _pause_dialog_and_user(
                    db,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    user=user,
                )
                output_context["should_pause"] = True
                results.append(ActionResult(action.id, action.action_type, "success"))
                continue

            if action.action_type == "send_message":
                template = str(cfg.get("message", "")).strip()
                rendered_message = _render_template(template, output_context)
                output_context.setdefault("messages_to_send", []).append(rendered_message)
                results.append(ActionResult(action.id, action.action_type, "success", {"message": rendered_message}))
                continue

            if action.action_type == "augment_prompt":
                extra = str(cfg.get("instruction", "")).strip()
                if extra:
                    output_context.setdefault("augment_prompt", []).append(extra)
                results.append(ActionResult(action.id, action.action_type, "success", {"instruction": extra}))
                continue

            if action.action_type == "set_result":
                result_text = _render_template(str(cfg.get("result", "")), output_context)
                output_context["forced_result"] = result_text
                results.append(ActionResult(action.id, action.action_type, "success", {"result": result_text}))
                continue

            if action.action_type == "webhook":
                tool_id = cfg.get("tool_id")
                template_context = dict(output_context)
                latest_tool_args = _extract_latest_tool_call_args(
                    output_context,
                    preferred_tool_name=str(output_context.get("tool_name") or ""),
                )
                if latest_tool_args:
                    template_context.setdefault("tool_call_args", latest_tool_args)
                    template_context.setdefault("tool_args", latest_tool_args)
                    for key, val in latest_tool_args.items():
                        template_context.setdefault(str(key), val)

                payload = _render_template(cfg.get("payload", {}), template_context)
                # Preferred mode: execute through saved Tool to reuse schema+mapping.
                if tool_id:
                    try:
                        tool_uuid = UUID(str(tool_id))
                    except ValueError as exc:
                        raise ValueError("invalid tool_id for webhook action") from exc

                    tool = await db.get(Tool, tool_uuid)
                    if (
                        not tool
                        or tool.is_deleted
                        or tool.status != "active"
                        or tool.execution_type != "http_webhook"
                        or not tool.endpoint
                    ):
                        raise ValueError("webhook tool is not available")

                    merged_args = payload if isinstance(payload, dict) else {}
                    if not isinstance(merged_args, dict):
                        raise ValueError("webhook payload must be object")

                    result_payload = await execute_tool_call(
                        endpoint=tool.endpoint,
                        input_schema=tool.input_schema,
                        args=merged_args,
                        trace_id=trace_id,
                        auth_type=tool.auth_type,
                        http_method=tool.http_method or "POST",
                        parameter_mapping=tool.parameter_mapping,
                        custom_headers=tool.custom_headers,
                        secrets_ref=None,
                        secret_payload=None,
                        allowed_domains=cfg.get("allowed_domains"),
                        timeout_ms=int(float(cfg.get("timeout_seconds", settings.function_rule_webhook_timeout_seconds)) * 1000),
                        user=user,
                    )
                    output_context["last_webhook_result"] = result_payload
                    results.append(
                        ActionResult(
                            action.id,
                            action.action_type,
                            "success",
                            {
                                "mode": "tool",
                                "tool_id": str(tool.id),
                                "tool_name": tool.name,
                                "method": (tool.http_method or "POST").upper(),
                                "host": urlparse(tool.endpoint).hostname,
                                "endpoint": tool.endpoint,
                                "args": _truncate_for_trace(merged_args),
                                "request_payload": _truncate_for_trace(merged_args),
                                "response": _truncate_for_trace(result_payload),
                            },
                        )
                    )
                    continue

                # Legacy mode: direct URL call from action config.
                url = str(cfg.get("url", "")).strip()
                method = str(cfg.get("method", "POST")).upper()
                if not url:
                    raise ValueError("webhook url is required")
                hostname = urlparse(url).hostname
                allowed_domains = cfg.get("allowed_domains")
                if isinstance(allowed_domains, list) and allowed_domains:
                    _ensure_allowed_domain(url, [str(item) for item in allowed_domains])
                headers = {str(k): str(v) for k, v in (cfg.get("headers") or {}).items()}
                headers.setdefault("x-idempotency-key", generate_idempotency_key())
                headers.setdefault("x-trace-id", trace_id)
                timeout_seconds = float(cfg.get("timeout_seconds", settings.function_rule_webhook_timeout_seconds))
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    if method == "GET":
                        response = await client.get(url, params=payload if isinstance(payload, dict) else None, headers=headers)
                    else:
                        response = await client.request(method, url, json=payload, headers=headers)
                response.raise_for_status()
                results.append(
                    ActionResult(
                        action.id,
                        action.action_type,
                        "success",
                        {
                            "mode": "direct",
                            "method": method,
                            "status_code": response.status_code,
                            "host": hostname,
                            "endpoint": url,
                            "args": _truncate_for_trace(payload),
                            "request_payload": _truncate_for_trace(payload),
                            "response": _truncate_for_trace(response.text),
                        },
                    )
                )
                continue

            results.append(ActionResult(action.id, action.action_type, "skipped", {"reason": "unsupported_action"}))
        except Exception as exc:  # noqa: BLE001
            logger.warning("rule_action_failed", action_type=action.action_type, error=str(exc), trace_id=trace_id)
            results.append(ActionResult(action.id, action.action_type, "error", {"error": str(exc)}))
        finally:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            if results:
                results[-1].details.setdefault("latency_ms", elapsed_ms)

    return results, output_context


async def write_rule_execution_log(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    rule_id: UUID,
    run_id: UUID | None,
    session_id: str,
    trace_id: str,
    trigger_phase: str,
    matched: bool,
    result_status: str,
    reason: str | None,
    latency_ms: int | None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        RuleExecutionLog(
            tenant_id=tenant_id,
            agent_id=agent_id,
            rule_id=rule_id,
            run_id=run_id,
            session_id=session_id,
            trace_id=trace_id,
            trigger_phase=trigger_phase,
            matched=matched,
            result_status=result_status,
            reason=reason,
            latency_ms=latency_ms,
            details=details,
        )
    )


async def run_rules_for_phase(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    session_id: str,
    trace_id: str,
    phase: str,
    message: str,
    user: AuthContext,
    run_id: UUID | None = None,
    context: dict[str, Any] | None = None,
    rules_enabled: bool = True,
    semantic_allowed: bool = True,
    tool_id_filter: UUID | None = None,
) -> tuple[list[RuleRuntimeResult], dict[str, Any]]:
    context_data = dict(context or {})
    context_data.setdefault("message", message)
    if not rules_enabled:
        return [], context_data
    stmt = (
        select(FunctionRule)
        .options(selectinload(FunctionRule.actions))
        .where(
            FunctionRule.tenant_id == tenant_id,
            FunctionRule.agent_id == agent_id,
            FunctionRule.enabled.is_(True),
        )
        .order_by(FunctionRule.priority.asc(), FunctionRule.created_at.asc())
    )
    if tool_id_filter is not None:
        stmt = stmt.where(FunctionRule.tool_id == tool_id_filter)
    else:
        stmt = stmt.where(FunctionRule.trigger_mode == phase)
    rules = (await db.execute(stmt)).scalars().all()
    settings = get_settings()
    max_rules = int(context_data.get("max_rules_per_phase") or settings.function_rules_max_per_phase)
    rules = rules[:max_rules]
    traces: list[RuleRuntimeResult] = []

    for rule in rules:
        started = time.monotonic()
        if tool_id_filter is not None:
            condition = ConditionResult(matched=True, score=1.0, reason="matched by linked tool execution")
        elif rule.condition_type == "semantic" and (not semantic_allowed or not rule.allow_semantic):
            condition = ConditionResult(matched=False, score=0.0, reason="semantic disabled by feature flag")
        else:
            condition = evaluate_condition(rule, message=message, context=context_data)
        status = "skipped"
        action_traces: list[ActionResult] = []
        if condition.matched:
            simulate_only = bool(context_data.get("simulate_only", False))
            status = "dry_run" if (rule.dry_run or simulate_only) else "success"
            if not rule.dry_run and not simulate_only:
                if rule.behavior_after_execution == "pause":
                    await _pause_dialog_and_user(
                        db,
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        session_id=session_id,
                        user=user,
                    )
                    context_data["should_pause"] = True
                elif rule.behavior_after_execution == "augment_prompt":
                    instruction = str((rule.condition_config or {}).get("augment_prompt", "")).strip()
                    if instruction:
                        context_data.setdefault("augment_prompt", []).append(instruction)

                if rule.reaction_to_execution == "send_message":
                    message_template = str((rule.condition_config or {}).get("reaction_message", "")).strip()
                    if message_template:
                        context_data.setdefault("messages_to_send", []).append(
                            _render_template(message_template, context_data)
                        )
                elif rule.reaction_to_execution == "silent":
                    context_data["silent_reaction"] = True
                elif rule.reaction_to_execution == "ai_instruction":
                    ai_instruction = str((rule.condition_config or {}).get("ai_instruction", "")).strip()
                    if ai_instruction:
                        context_data.setdefault("augment_prompt", []).append(ai_instruction)

                if not context_data.get("skip_rule_tool_execution"):
                    tool_result, rule_tool_trace = await _execute_rule_tool(
                        db,
                        rule=rule,
                        context=context_data,
                        trace_id=trace_id,
                        user=user,
                    )
                    if tool_result is not None:
                        context_data["last_tool_result"] = tool_result
                    if rule_tool_trace is not None:
                        action_traces.append(rule_tool_trace)
                post_action_traces, context_data = await execute_post_actions(
                    db,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    trace_id=trace_id,
                    user=user,
                    actions=rule.actions,
                    execution_status="success",
                    context=context_data,
                )
                action_traces.extend(post_action_traces)
            if rule.stop_on_match:
                stop_reason = "stop_on_match"
                elapsed = int((time.monotonic() - started) * 1000)
                await write_rule_execution_log(
                    db,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    rule_id=rule.id,
                    run_id=run_id,
                    session_id=session_id,
                    trace_id=trace_id,
                    trigger_phase=phase,
                    matched=condition.matched,
                    result_status=status,
                    reason=condition.reason or stop_reason,
                    latency_ms=elapsed,
                    details={"score": condition.score, "should_pause": bool(context_data.get("should_pause", False)), **condition.details},
                )
                traces.append(
                    RuleRuntimeResult(
                        rule_id=rule.id,
                        matched=True,
                        score=condition.score,
                        reason=condition.reason,
                        actions=action_traces,
                    )
                )
                break

        elapsed_ms = int((time.monotonic() - started) * 1000)
        await write_rule_execution_log(
            db,
            tenant_id=tenant_id,
            agent_id=agent_id,
            rule_id=rule.id,
            run_id=run_id,
            session_id=session_id,
            trace_id=trace_id,
            trigger_phase=phase,
            matched=condition.matched,
            result_status=status,
            reason=condition.reason,
            latency_ms=elapsed_ms,
            details={"score": condition.score, "should_pause": bool(context_data.get("should_pause", False)), **condition.details},
        )
        traces.append(
            RuleRuntimeResult(
                rule_id=rule.id,
                matched=condition.matched,
                score=condition.score,
                reason=condition.reason,
                actions=action_traces,
            )
        )

    return traces, context_data
