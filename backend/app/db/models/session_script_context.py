from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin


class SessionScriptContext(Base, UUIDPrimaryKeyMixin):
    """
    Tracks expert-script navigation state per agent session.

    One row per (agent_id, session_id) pair.  The row is upserted on every
    navigate_script call so the runtime always has fresh context without
    loading the full message history.
    """

    __tablename__ = "session_script_contexts"

    agent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), index=True, unique=True, nullable=False
    )

    topics_discussed: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    objection_attempts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    detected_service_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    detected_employee_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    current_node_ref_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── motive-aware runtime (migration 0077) ────────────────────────────
    # Идентификаторы AgentKgEntity, которые были выявлены/использованы
    # в ходе диалога. Хранятся как UUID-строки в JSONB-массивах, чтобы
    # не заводить М2М-таблицы ради быстрого read-modify-write.
    detected_motive_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    raised_objection_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    closed_objection_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    asked_followup_questions: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    shown_proof_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    # tactic_node_ref строковые ключи (flow_id#node_ref) — тактики,
    # которые уже пробовались и не привели к сдвигу по воронке.
    blocked_tactic_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    emotional_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    funnel_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    emotional_pause_used: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Последняя диагностика (полный JSON ответа diagnose_client_motive) —
    # используется как fallback-источник при сборке snapshot для LLM.
    last_diagnosis: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Стиль последнего сработавшего топ-матча из search_script_flows.
    # Сохраняется после каждого успешного поиска и инжектируется в системный
    # промпт следующего хода как «закон» — LLM обязана следовать ему даже
    # если не вызвала search_script_flows в текущем ходу.
    last_tactic_style: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
