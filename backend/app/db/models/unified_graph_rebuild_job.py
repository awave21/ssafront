from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class UnifiedGraphRebuildJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "unified_graph_rebuild_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_unified_graph_rebuild_jobs_status",
        ),
        CheckConstraint(
            "progress_pct >= 0 AND progress_pct <= 100",
            name="ck_unified_graph_rebuild_jobs_progress_pct",
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
    active_sqns_only: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
