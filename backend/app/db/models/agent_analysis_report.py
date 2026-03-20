from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AgentAnalysisReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_analysis_reports"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_analysis_jobs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    analysis_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    kpis: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    topics: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    top_failure_topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    recommendation_count_by_category: Mapped[dict[str, int]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    raw_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
