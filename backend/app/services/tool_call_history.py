from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
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


class ToolCallHistoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self, *, tenant_id: UUID, query: ToolCallHistoryQuery) -> ToolCallHistoryResponse:
        start_utc, end_utc = _resolve_utc_range(query.date_from, query.date_to, query.timezone)

        filters: list[Any] = [
            ToolCallLog.tenant_id == tenant_id,
            ToolCallLog.invoked_at >= start_utc,
            ToolCallLog.invoked_at < end_utc,
        ]

        if query.agent_id:
            try:
                agent_uuid = UUID(query.agent_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("Invalid agent_id") from exc
            filters.append(ToolCallLog.agent_id == agent_uuid)

        if query.tool_name:
            filters.append(ToolCallLog.tool_name == query.tool_name)

        if query.status:
            filters.append(ToolCallLog.status == query.status)

        if query.search:
            term = f"%{query.search.strip()}%"
            if term != "%%":
                filters.append(
                    or_(
                        ToolCallLog.tool_name.ilike(term),
                        Agent.name.ilike(term),
                        cast(ToolCallLog.user_info, String).ilike(term),
                        cast(ToolCallLog.request_payload, String).ilike(term),
                    )
                )

        where_clause = and_(*filters)

        total_stmt = (
            select(func.count())
            .select_from(ToolCallLog)
            .join(Agent, Agent.id == ToolCallLog.agent_id)
            .where(where_clause)
        )
        total = int((await self.db.execute(total_stmt)).scalar_one() or 0)

        items_stmt = (
            select(ToolCallLog, Agent)
            .join(Agent, Agent.id == ToolCallLog.agent_id)
            .where(where_clause)
            .order_by(ToolCallLog.invoked_at.desc())
            .limit(query.limit)
            .offset(query.offset)
        )
        rows = (await self.db.execute(items_stmt)).all()

        items: list[ToolCallHistoryItem] = []
        for log_row, agent_row in rows:
            request_payload = _as_dict(log_row.request_payload)
            response_payload = _as_dict(log_row.response_payload)
            error_payload = _as_dict(log_row.error_payload)
            user_info = _as_dict(log_row.user_info) or {}
            params: list[ToolCallHistoryParamItem] = []
            if isinstance(request_payload, dict):
                for key, value in sorted(request_payload.items(), key=lambda item: item[0]):
                    params.append(ToolCallHistoryParamItem(key=str(key), value=value))

            items.append(
                ToolCallHistoryItem(
                    id=str(log_row.id),
                    tool_name=log_row.tool_name,
                    tool_description=log_row.tool_description or log_row.tool_name,
                    tool_settings_url=log_row.tool_settings_url or f"/agents/{agent_row.id}",
                    status="success" if log_row.status == "success" else "error",
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

        return ToolCallHistoryResponse(
            items=items,
            total=total,
            limit=query.limit,
            offset=query.offset,
        )
