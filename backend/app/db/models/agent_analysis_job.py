from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AgentAnalysisJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_analysis_jobs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "agent_id",
            "idempotency_key",
            name="uq_agent_analysis_jobs_tenant_agent_idempotency_key",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_agent_analysis_jobs_status",
        ),
        CheckConstraint(
            "stage IN ('queued', 'collecting', 'analyzing', 'persisting', 'done', 'failed', 'cancelled')",
            name="ck_agent_analysis_jobs_stage",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", server_default="queued")
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="queued", server_default="queued")
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    only_with_manager: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    max_dialogs: Mapped[int] = mapped_column(Integer, nullable=False)
    history_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    max_tokens_per_job: Mapped[int] = mapped_column(Integer, nullable=False)
    max_llm_requests_per_job: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    llm_requests_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    analysis_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    cancelled_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
