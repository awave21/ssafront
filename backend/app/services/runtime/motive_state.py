"""Управление motive-aware состоянием диалога (`SessionScriptContext`).

Отвечает за:
- загрузку/инициализацию state по (agent_id, session_id);
- безопасное дописывание выявленных мотивов/возражений/вопросов;
- генерацию компактного snapshot-блока для системного промпта LLM.

Используется двумя тулами: `diagnose_client_motive` (пишет state после
диагностики) и `search_script_flows` (читает state для rerank-а матчей).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session_script_context import SessionScriptContext

logger = structlog.get_logger(__name__)


EMOTIONAL_BUFFER_STATES: frozenset[str] = frozenset({"anxious", "angry"})
FUNNEL_STAGES: tuple[str, ...] = (
    "discovery",
    "consideration",
    "objection",
    "closing",
    "post_sale",
)


@dataclass
class MotiveState:
    """Удобный in-memory вид SessionScriptContext для runtime-логики."""

    session_id: UUID
    agent_id: UUID
    tenant_id: UUID
    detected_motive_ids: list[str]
    raised_objection_ids: list[str]
    closed_objection_ids: list[str]
    asked_followup_questions: list[str]
    shown_proof_ids: list[str]
    blocked_tactic_ids: list[str]
    emotional_state: str | None
    funnel_stage: str | None
    emotional_pause_used: bool
    last_diagnosis: dict[str, Any] | None
    detected_service_id: str | None
    detected_employee_id: str | None
    # Стиль топ-матча из последнего вызова search_script_flows.
    # В runtime_bridges_mode=auto инжектируется в system prompt; в manual — только в tool result.
    last_tactic_style: dict[str, Any] | None

    @classmethod
    def empty(cls, *, session_id: UUID, agent_id: UUID, tenant_id: UUID) -> "MotiveState":
        return cls(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            detected_motive_ids=[],
            raised_objection_ids=[],
            closed_objection_ids=[],
            asked_followup_questions=[],
            shown_proof_ids=[],
            blocked_tactic_ids=[],
            emotional_state=None,
            funnel_stage=None,
            emotional_pause_used=False,
            last_diagnosis=None,
            detected_service_id=None,
            detected_employee_id=None,
            last_tactic_style=None,
        )

    @classmethod
    def from_row(cls, row: SessionScriptContext) -> "MotiveState":
        return cls(
            session_id=row.session_id,
            agent_id=row.agent_id,
            tenant_id=row.tenant_id,
            detected_motive_ids=_ensure_str_list(row.detected_motive_ids),
            raised_objection_ids=_ensure_str_list(row.raised_objection_ids),
            closed_objection_ids=_ensure_str_list(row.closed_objection_ids),
            asked_followup_questions=_ensure_str_list(row.asked_followup_questions),
            shown_proof_ids=_ensure_str_list(row.shown_proof_ids),
            blocked_tactic_ids=_ensure_str_list(row.blocked_tactic_ids),
            emotional_state=row.emotional_state,
            funnel_stage=row.funnel_stage,
            emotional_pause_used=bool(row.emotional_pause_used),
            last_diagnosis=row.last_diagnosis if isinstance(row.last_diagnosis, dict) else None,
            detected_service_id=str(row.detected_service_id)
            if getattr(row, "detected_service_id", None)
            else None,
            detected_employee_id=str(row.detected_employee_id)
            if getattr(row, "detected_employee_id", None)
            else None,
            last_tactic_style=row.last_tactic_style
            if isinstance(getattr(row, "last_tactic_style", None), dict)
            else None,
        )


def _ensure_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if v is not None]


def _merge_unique(existing: Iterable[str], incoming: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in list(existing) + list(incoming):
        s = str(v)
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


async def load_motive_state(
    db: AsyncSession,
    *,
    session_id: UUID,
    agent_id: UUID,
    tenant_id: UUID,
) -> MotiveState:
    """Грузит текущее motive-state по session_id или возвращает пустой.

    Не создаёт строку в БД — для этого используется `upsert_motive_state`.
    """
    stmt = select(SessionScriptContext).where(
        SessionScriptContext.session_id == session_id
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return MotiveState.empty(
            session_id=session_id, agent_id=agent_id, tenant_id=tenant_id
        )
    return MotiveState.from_row(row)


async def upsert_motive_state(
    db: AsyncSession,
    *,
    session_id: UUID,
    agent_id: UUID,
    tenant_id: UUID,
    detected_motive_ids: list[str] | None = None,
    raised_objection_ids: list[str] | None = None,
    closed_objection_ids: list[str] | None = None,
    asked_followup_questions: list[str] | None = None,
    shown_proof_ids: list[str] | None = None,
    blocked_tactic_ids: list[str] | None = None,
    emotional_state: str | None = None,
    funnel_stage: str | None = None,
    emotional_pause_used: bool | None = None,
    last_diagnosis: dict[str, Any] | None = None,
    last_tactic_style: dict[str, Any] | None = None,
) -> MotiveState:
    """
    Апсертит строку state. Списочные поля мёржатся (union), скалярные
    перезаписываются только если передан не-None.

    На INSERT — проставляем defaults, на UPDATE — используем SQL-выражения
    для безопасного мёржа массивов (через jsonb_*). Но чтобы не тащить
    сложный SQL в каждую запись, делаем read-modify-write в питоне:
    это ок для нашего write-rate (≤1 запись на реплику клиента).
    """
    stmt = select(SessionScriptContext).where(
        SessionScriptContext.session_id == session_id
    )
    row = (await db.execute(stmt)).scalar_one_or_none()

    if row is None:
        row = SessionScriptContext(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            topics_discussed=[],
            objection_attempts={},
            detected_motive_ids=[],
            raised_objection_ids=[],
            closed_objection_ids=[],
            asked_followup_questions=[],
            shown_proof_ids=[],
            blocked_tactic_ids=[],
            emotional_pause_used=False,
        )
        db.add(row)

    if detected_motive_ids is not None:
        row.detected_motive_ids = _merge_unique(row.detected_motive_ids or [], detected_motive_ids)
    if raised_objection_ids is not None:
        row.raised_objection_ids = _merge_unique(row.raised_objection_ids or [], raised_objection_ids)
    if closed_objection_ids is not None:
        row.closed_objection_ids = _merge_unique(row.closed_objection_ids or [], closed_objection_ids)
    if asked_followup_questions is not None:
        row.asked_followup_questions = _merge_unique(
            row.asked_followup_questions or [], asked_followup_questions
        )
    if shown_proof_ids is not None:
        row.shown_proof_ids = _merge_unique(row.shown_proof_ids or [], shown_proof_ids)
    if blocked_tactic_ids is not None:
        row.blocked_tactic_ids = _merge_unique(row.blocked_tactic_ids or [], blocked_tactic_ids)
    if emotional_state is not None:
        row.emotional_state = emotional_state or None
    if funnel_stage is not None:
        row.funnel_stage = funnel_stage or None
    if emotional_pause_used is not None:
        row.emotional_pause_used = bool(emotional_pause_used)
    if last_diagnosis is not None:
        row.last_diagnosis = last_diagnosis
    if last_tactic_style is not None:
        row.last_tactic_style = last_tactic_style

    await db.flush()
    return MotiveState.from_row(row)


# Используется, когда upsert уже не нужен, но надо упомянуть proof/вопрос
# пост-фактум (например, агент в ответе задал вопрос — трекаем).
async def touch_motive_state_lists(
    db: AsyncSession,
    *,
    session_id: UUID,
    agent_id: UUID,
    tenant_id: UUID,
    **list_fields: list[str],
) -> None:
    await upsert_motive_state(
        db,
        session_id=session_id,
        agent_id=agent_id,
        tenant_id=tenant_id,
        **list_fields,  # type: ignore[arg-type]
    )


def render_state_snapshot(state: MotiveState, *, entity_names: dict[str, str] | None = None) -> str:
    """Короткий man-readable snapshot для системного промпта.

    Показывает LLM только то, что может повлиять на следующую реплику:
    выявленные мотивы, ещё не закрытые возражения, уже заданные follow-up
    вопросы (чтобы не повторяться), эмоциональное состояние, стадия.

    `entity_names` — опциональный маппинг id → human-readable имя (name из
    `agent_kg_entities`); если не передан, пишем raw id.
    """
    names = entity_names or {}

    def _render_ids(ids: list[str]) -> str:
        if not ids:
            return "—"
        labels = [names.get(i, i[:8] + "…") for i in ids[:8]]
        return ", ".join(labels)

    open_objections = [
        oid
        for oid in state.raised_objection_ids
        if oid not in state.closed_objection_ids
    ]

    lines = ["=== СОСТОЯНИЕ ДИАЛОГА (что LLM должна учесть) ==="]

    if state.funnel_stage:
        lines.append(f"Стадия воронки: {state.funnel_stage}")
    if state.emotional_state:
        lines.append(f"Эмоциональное состояние клиента: {state.emotional_state}")
    if state.emotional_pause_used:
        lines.append("Эмо-пауза уже использовалась в этом диалоге.")

    lines.append(f"Выявленные мотивы: {_render_ids(state.detected_motive_ids)}")
    lines.append(f"Открытые возражения: {_render_ids(open_objections)}")
    if state.closed_objection_ids:
        lines.append(f"Уже закрыто возражений: {len(state.closed_objection_ids)}")
    if state.asked_followup_questions:
        n = len(state.asked_followup_questions)
        lines.append(
            f"Follow-up вопросы уже заданы ({n} шт.) — НЕ ПОВТОРЯЙ ИХ ДОСЛОВНО:"
        )
        for q in state.asked_followup_questions[-5:]:
            lines.append(f"  • «{q}»")
    if state.shown_proof_ids:
        lines.append(
            f"Уже показано доказательств: {len(state.shown_proof_ids)} — старайся не дублировать"
        )
    if state.blocked_tactic_ids:
        lines.append(
            f"Тактики, не давшие сдвига: {_render_ids(state.blocked_tactic_ids)} — избегай"
        )

    lines.append("=== /СОСТОЯНИЕ ===")
    return "\n".join(lines)


def is_state_empty(state: MotiveState) -> bool:
    """Если state пустой — snapshot можно не подсовывать в промпт."""
    return not any(
        [
            state.detected_motive_ids,
            state.raised_objection_ids,
            state.closed_objection_ids,
            state.asked_followup_questions,
            state.shown_proof_ids,
            state.blocked_tactic_ids,
            state.emotional_state,
            state.funnel_stage,
            state.emotional_pause_used,
        ]
    )


# Оставлено для будущего: ON CONFLICT DO UPDATE с полным JSONB merge
# через SQL — пока не используется, read-modify-write хватает.
_PG_UPSERT_SENTINEL = pg_insert  # noqa: F841  (чтобы импорт не вылетел в lint)
