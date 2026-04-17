from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import String, and_, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.function_rule import FunctionRule
from app.db.models.rule_execution_log import RuleExecutionLog
from app.db.models.tool_call_log import ToolCallLog
from app.schemas.tool_call_history import (
    ToolCallHistoryAgentRef,
    ToolCallHistoryItem,
    ToolCallHistoryParamItem,
    ToolCallHistoryQuery,
    ToolCallHistoryResponse,
)


def _parse_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo((timezone_name or "UTC").strip() or "UTC")
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Invalid timezone") from exc


def _resolve_utc_range(date_from: date, date_to: date, timezone_name: str) -> tuple[datetime, datetime]:
    if date_to < date_from:
        raise ValueError("date_to cannot be earlier than date_from")
    tz = _parse_timezone(timezone_name)
    start_local = datetime.combine(date_from, time.min, tzinfo=tz)
    end_local_exclusive = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local_exclusive.astimezone(timezone.utc)


def _as_dict(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload
    return {"value": payload}


def _rule_log_to_ui_status(result_status: str) -> str:
    if result_status == "error":
        return "error"
    if result_status == "skipped":
        return "skipped"
    if result_status == "dry_run":
        return "dry_run"
    return "success"


class ToolCallHistoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self, *, tenant_id: UUID, query: ToolCallHistoryQuery) -> ToolCallHistoryResponse:
        start_utc, end_utc = _resolve_utc_range(query.date_from, query.date_to, query.timezone)

        agent_uuid: UUID | None = None
        if query.agent_id:
            try:
                agent_uuid = UUID(query.agent_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("Invalid agent_id") from exc

        tool_filters: list[Any] = [
            ToolCallLog.tenant_id == tenant_id,
            ToolCallLog.invoked_at >= start_utc,
            ToolCallLog.invoked_at < end_utc,
        ]

        if agent_uuid is not None:
            tool_filters.append(ToolCallLog.agent_id == agent_uuid)

        if query.tool_name:
            tool_filters.append(ToolCallLog.tool_name == query.tool_name)

        if query.status:
            tool_filters.append(ToolCallLog.status == query.status)

        if query.search:
            term = f"%{query.search.strip()}%"
            if term != "%%":
                tool_filters.append(
                    or_(
                        ToolCallLog.tool_name.ilike(term),
                        Agent.name.ilike(term),
                        cast(ToolCallLog.user_info, String).ilike(term),
                        cast(ToolCallLog.request_payload, String).ilike(term),
                    )
                )

        tool_where = and_(*tool_filters)

        stmt_tool = (
            select(
                literal("tool").label("entry_type"),
                cast(ToolCallLog.id, String).label("entry_id"),
                ToolCallLog.invoked_at.label("event_at"),
            )
            .select_from(ToolCallLog)
            .join(Agent, Agent.id == ToolCallLog.agent_id)
            .where(tool_where)
        )

        union_parts: list[Any] = [stmt_tool]

        include_scenarios = not query.tool_name
        if include_scenarios:
            scenario_filters: list[Any] = [
                RuleExecutionLog.tenant_id == tenant_id,
                RuleExecutionLog.created_at >= start_utc,
                RuleExecutionLog.created_at < end_utc,
            ]

            if agent_uuid is not None:
                scenario_filters.append(RuleExecutionLog.agent_id == agent_uuid)

            if query.status == "success":
                scenario_filters.append(RuleExecutionLog.result_status.in_(["success", "dry_run"]))
            elif query.status == "error":
                scenario_filters.append(RuleExecutionLog.result_status == "error")
            elif query.status == "skipped":
                scenario_filters.append(RuleExecutionLog.result_status == "skipped")
            elif query.status == "dry_run":
                scenario_filters.append(RuleExecutionLog.result_status == "dry_run")

            if query.search:
                term = f"%{query.search.strip()}%"
                if term != "%%":
                    scenario_filters.append(
                        or_(
                            FunctionRule.name.ilike(term),
                            RuleExecutionLog.reason.ilike(term),
                            cast(RuleExecutionLog.details, String).ilike(term),
                            RuleExecutionLog.session_id.ilike(term),
                            RuleExecutionLog.trace_id.ilike(term),
                            Agent.name.ilike(term),
                        )
                    )

            scenario_where = and_(*scenario_filters)
            stmt_scenario = (
                select(
                    literal("scenario").label("entry_type"),
                    cast(RuleExecutionLog.id, String).label("entry_id"),
                    RuleExecutionLog.created_at.label("event_at"),
                )
                .select_from(RuleExecutionLog)
                .join(Agent, Agent.id == RuleExecutionLog.agent_id)
                .join(FunctionRule, FunctionRule.id == RuleExecutionLog.rule_id)
                .where(scenario_where)
            )
            union_parts.append(stmt_scenario)

        if len(union_parts) == 1:
            u = stmt_tool.subquery("u")
        else:
            u = union_all(*union_parts).subquery("u")

        total_stmt = select(func.count()).select_from(u)
        total = int((await self.db.execute(total_stmt)).scalar_one() or 0)

        page_stmt = (
            select(u.c.entry_type, u.c.entry_id, u.c.event_at)
            .select_from(u)
            .order_by(u.c.event_at.desc())
            .limit(query.limit)
            .offset(query.offset)
        )
        page_rows = (await self.db.execute(page_stmt)).all()

        tool_ids: list[UUID] = []
        scenario_ids: list[UUID] = []
        order: list[tuple[str, str]] = []
        for entry_type, entry_id, _event_at in page_rows:
            order.append((entry_type, entry_id))
            try:
                uid = UUID(entry_id)
            except (TypeError, ValueError):
                continue
            if entry_type == "tool":
                tool_ids.append(uid)
            else:
                scenario_ids.append(uid)

        tool_map: dict[str, tuple[ToolCallLog, Agent]] = {}
        if tool_ids:
            t_stmt = (
                select(ToolCallLog, Agent)
                .join(Agent, Agent.id == ToolCallLog.agent_id)
                .where(ToolCallLog.id.in_(tool_ids))
            )
            for log_row, agent_row in (await self.db.execute(t_stmt)).all():
                tool_map[str(log_row.id)] = (log_row, agent_row)

        scenario_map: dict[str, tuple[RuleExecutionLog, Agent, FunctionRule]] = {}
        if scenario_ids:
            s_stmt = (
                select(RuleExecutionLog, Agent, FunctionRule)
                .join(Agent, Agent.id == RuleExecutionLog.agent_id)
                .join(FunctionRule, FunctionRule.id == RuleExecutionLog.rule_id)
                .where(RuleExecutionLog.id.in_(scenario_ids))
            )
            for log_row, agent_row, rule_row in (await self.db.execute(s_stmt)).all():
                scenario_map[str(log_row.id)] = (log_row, agent_row, rule_row)

        items: list[ToolCallHistoryItem] = []
        for entry_type, entry_id, _event_at in page_rows:
            if entry_type == "tool":
                pair = tool_map.get(entry_id)
                if not pair:
                    continue
                log_row, agent_row = pair
                request_payload = _as_dict(log_row.request_payload)
                response_payload = _as_dict(log_row.response_payload)
                error_payload = _as_dict(log_row.error_payload)
                user_info = _as_dict(log_row.user_info) or {}
                params: list[ToolCallHistoryParamItem] = []
                if isinstance(request_payload, dict):
                    for key, value in sorted(request_payload.items(), key=lambda item: item[0]):
                        params.append(ToolCallHistoryParamItem(key=str(key), value=value))

                st: str = "success" if log_row.status == "success" else "error"
                items.append(
                    ToolCallHistoryItem(
                        entry_type="tool",
                        id=str(log_row.id),
                        tool_name=log_row.tool_name,
                        tool_description=log_row.tool_description or log_row.tool_name,
                        tool_settings_url=log_row.tool_settings_url or f"/agents/{agent_row.id}",
                        status=st,  # type: ignore[arg-type]
                        invoked_at=log_row.invoked_at,
                        duration_ms=log_row.duration_ms,
                        agent=ToolCallHistoryAgentRef(id=str(agent_row.id), name=agent_row.name),
                        user_info=user_info,
                        params=params,
                        request_payload=request_payload,
                        response_payload=response_payload,
                        error_payload=error_payload,
                    )
                )
            else:
                triple = scenario_map.get(entry_id)
                if not triple:
                    continue
                log_row, agent_row, rule_row = triple
                ui_status = _rule_log_to_ui_status(log_row.result_status)
                details = log_row.details if isinstance(log_row.details, dict) else {}
                params_sc: list[ToolCallHistoryParamItem] = []
                if isinstance(details, dict):
                    for key, value in sorted(details.items(), key=lambda item: str(item[0])):
                        params_sc.append(ToolCallHistoryParamItem(key=str(key), value=value))

                desc = f"Фаза: {log_row.trigger_phase}"
                if log_row.matched:
                    desc += " · условие совпало"
                else:
                    desc += " · условие не совпало"

                req_payload = {
                    "session_id": log_row.session_id,
                    "trace_id": log_row.trace_id,
                    "trigger_phase": log_row.trigger_phase,
                    "matched": log_row.matched,
                    "run_id": str(log_row.run_id) if log_row.run_id else None,
                }
                err_pl: dict[str, Any] | None = None
                if log_row.result_status == "error" and log_row.reason:
                    err_pl = {"reason": log_row.reason}

                items.append(
                    ToolCallHistoryItem(
                        entry_type="scenario",
                        id=str(log_row.id),
                        tool_name=rule_row.name,
                        tool_description=desc,
                        tool_settings_url=f"/agents/{agent_row.id}/scenarios",
                        status=ui_status,  # type: ignore[arg-type]
                        invoked_at=log_row.created_at,
                        duration_ms=log_row.latency_ms,
                        agent=ToolCallHistoryAgentRef(id=str(agent_row.id), name=agent_row.name),
                        user_info={},
                        params=params_sc,
                        request_payload=req_payload,
                        response_payload=details or None,
                        error_payload=err_pl,
                        rule_id=str(rule_row.id),
                        rule_name=rule_row.name,
                        trigger_phase=log_row.trigger_phase,
                        matched=log_row.matched,
                        rule_result_status=log_row.result_status,
                        reason=log_row.reason,
                    )
                )

        return ToolCallHistoryResponse(
            items=items,
            total=total,
            limit=query.limit,
            offset=query.offset,
        )
