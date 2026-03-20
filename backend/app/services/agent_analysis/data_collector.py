from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.run import Run
from app.db.models.session_message import SessionMessage
from app.services.agent_analysis.redaction import redact_any, redact_text
from app.utils.message_mapping import extract_structured_parts, infer_role


@dataclass
class AnalysisDialogMessage:
    message_id: UUID
    run_id: UUID
    role: str
    content: str
    created_at: datetime


@dataclass
class AnalysisToolEvent:
    event_type: str
    tool_name: str | None
    tool_call_id: str | None
    args: dict[str, Any] | None
    result: Any | None
    run_id: UUID
    message_id: UUID
    error: str | None = None


@dataclass
class AnalysisDialogSample:
    session_id: str
    messages: list[AnalysisDialogMessage] = field(default_factory=list)
    tool_events: list[AnalysisToolEvent] = field(default_factory=list)
    has_manager_intervention: bool = False
    last_message_at: datetime | None = None
    dominant_language: str = "unknown"


def _extract_text(message_payload: dict[str, Any]) -> str:
    text_parts: list[str] = []
    for part in extract_structured_parts(message_payload):
        if part.get("kind") == "text":
            value = str(part.get("content") or "").strip()
            if value:
                text_parts.append(value)
    if text_parts:
        return "\n".join(text_parts)
    direct = message_payload.get("content")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    return ""


def _detect_language(samples: list[str]) -> str:
    joined = " ".join(samples)
    if not joined:
        return "unknown"
    cyrillic = sum(1 for ch in joined if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    latin = sum(1 for ch in joined if "a" <= ch.lower() <= "z")
    if cyrillic and latin:
        return "mixed"
    if cyrillic:
        return "ru"
    if latin:
        return "en"
    return "unknown"


def _base_dialogs_dict(session_ids: list[str]) -> dict[str, AnalysisDialogSample]:
    return {session_id: AnalysisDialogSample(session_id=session_id) for session_id in session_ids}


async def _load_candidate_session_ids(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    period_start: datetime,
    period_end: datetime,
    max_dialogs: int,
) -> list[str]:
    stmt: Select[Any] = (
        select(
            Run.session_id,
            func.max(Run.created_at).label("last_message_at"),
        )
        .where(
            Run.tenant_id == tenant_id,
            Run.agent_id == agent_id,
            Run.created_at >= period_start,
            Run.created_at <= period_end,
        )
        .group_by(Run.session_id)
        .order_by(func.max(Run.created_at).desc())
        .limit(max_dialogs)
    )
    result = await db.execute(stmt)
    return [row.session_id for row in result]


async def collect_dialog_samples(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    period_start: datetime,
    period_end: datetime,
    history_limit: int,
    max_dialogs: int,
    only_with_manager: bool,
) -> list[AnalysisDialogSample]:
    session_ids = await _load_candidate_session_ids(
        db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        period_start=period_start,
        period_end=period_end,
        max_dialogs=max_dialogs,
    )
    if not session_ids:
        return []

    dialogs = _base_dialogs_dict(session_ids)

    run_stmt = (
        select(Run.id, Run.status, Run.error_message, Run.tools_called)
        .where(
            Run.tenant_id == tenant_id,
            Run.agent_id == agent_id,
            Run.session_id.in_(session_ids),
        )
    )
    run_rows = await db.execute(run_stmt)
    run_meta: dict[UUID, dict[str, Any]] = {
        row.id: {
            "status": row.status,
            "error_message": row.error_message,
            "tools_called": row.tools_called if isinstance(row.tools_called, list) else [],
        }
        for row in run_rows
    }

    msg_stmt = (
        select(SessionMessage)
        .join(Run, SessionMessage.run_id == Run.id)
        .where(
            SessionMessage.tenant_id == tenant_id,
            SessionMessage.session_id.in_(session_ids),
            Run.agent_id == agent_id,
            Run.tenant_id == tenant_id,
        )
        .order_by(SessionMessage.session_id.asc(), SessionMessage.message_index.desc())
    )
    msg_rows = (await db.execute(msg_stmt)).scalars().all()

    per_session_counts: dict[str, int] = {}
    language_samples: dict[str, list[str]] = {session_id: [] for session_id in session_ids}

    for db_msg in msg_rows:
        session_id = db_msg.session_id
        current_count = per_session_counts.get(session_id, 0)
        if current_count >= history_limit:
            continue

        payload = db_msg.message if isinstance(db_msg.message, dict) else {}
        role = infer_role(payload)
        text = redact_text(_extract_text(payload))
        if not text and role != "manager":
            # Сообщения без текста оставляем только если там будут tool-events.
            text = ""

        dialog = dialogs[session_id]
        dialog.messages.append(
            AnalysisDialogMessage(
                message_id=db_msg.id,
                run_id=db_msg.run_id,
                role=role,
                content=text,
                created_at=db_msg.created_at,
            )
        )
        if text and role in {"user", "agent", "manager"}:
            language_samples[session_id].append(text)

        if role == "manager":
            dialog.has_manager_intervention = True
        if dialog.last_message_at is None or db_msg.created_at > dialog.last_message_at:
            dialog.last_message_at = db_msg.created_at

        for part in extract_structured_parts(payload):
            kind = part.get("kind")
            if kind not in {"tool-call", "tool-return"}:
                continue
            dialog.tool_events.append(
                AnalysisToolEvent(
                    event_type="tool_call" if kind == "tool-call" else "tool_result",
                    tool_name=part.get("tool_name"),
                    tool_call_id=part.get("tool_call_id"),
                    args=redact_any(part.get("args")) if isinstance(part.get("args"), dict) else None,
                    result=redact_any(part.get("result")),
                    run_id=db_msg.run_id,
                    message_id=db_msg.id,
                )
            )

        run_info = run_meta.get(db_msg.run_id) or {}
        run_tools = run_info.get("tools_called") or []
        for tool_call in run_tools:
            if not isinstance(tool_call, dict):
                continue
            dialog.tool_events.append(
                AnalysisToolEvent(
                    event_type="run_tool_call",
                    tool_name=tool_call.get("name"),
                    tool_call_id=tool_call.get("tool_call_id"),
                    args=redact_any(tool_call.get("args")) if isinstance(tool_call.get("args"), dict) else None,
                    result=redact_any(tool_call.get("result")),
                    run_id=db_msg.run_id,
                    message_id=db_msg.id,
                    error=redact_text(str(run_info.get("error_message"))) if run_info.get("error_message") else None,
                )
            )

        per_session_counts[session_id] = current_count + 1

    samples: list[AnalysisDialogSample] = []
    for session_id in session_ids:
        dialog = dialogs[session_id]
        dialog.messages.sort(key=lambda item: item.created_at)
        dialog.dominant_language = _detect_language(language_samples.get(session_id, []))
        if only_with_manager and not dialog.has_manager_intervention:
            continue
        if not dialog.messages:
            continue
        samples.append(dialog)

    return samples
