from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DirectQuestionFollowupJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "direct_question_followup_jobs"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "direct_question_id",
            "session_id",
            name="uq_dq_followup_job_run_question_session",
        ),
        Index(
            "idx_dq_followup_jobs_pending_schedule",
            "status",
            "scheduled_at",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    direct_question_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("direct_questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    channel_type: Mapped[str] = mapped_column(
        Enum("telegram", name="direct_question_followup_channel_type"),
        nullable=False,
    )
    channel_target: Mapped[str] = mapped_column(String(200), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("pending", "sent", "failed", "cancelled", name="direct_question_followup_status"),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
