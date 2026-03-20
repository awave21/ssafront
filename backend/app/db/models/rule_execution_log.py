from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RuleExecutionLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rule_execution_logs"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    rule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("function_rules.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    session_id: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    trigger_phase: Mapped[str] = mapped_column(String(30), default="pre_run", server_default="pre_run", nullable=False)
    matched: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    result_status: Mapped[str] = mapped_column(
        Enum("success", "error", "dry_run", "skipped", name="rule_execution_status"),
        default="success",
        server_default="success",
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    approval_status: Mapped[str | None] = mapped_column(
        Enum("pending_approval", "approved", "denied", "expired", name="rule_approval_status"),
        nullable=True,
    )
    approval_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
