from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.session_message import SessionMessage
    from app.db.models.run_token_usage_step import RunTokenUsageStep


class Run(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "runs"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("queued", "running", "succeeded", "failed", name="run_status"),
        default="queued",
        nullable=False,
    )
    input_message: Mapped[str] = mapped_column(Text, nullable=False)
    output_message: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str] = mapped_column(String(200), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    messages: Mapped[list[dict] | None] = mapped_column(JSONB)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD", nullable=False)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    cost_rub: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    cost_usd_logfire: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    logfire_reconcile_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        server_default="pending",
        nullable=False,
    )
    logfire_reconcile_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    logfire_reconcile_error: Mapped[str | None] = mapped_column(Text)
    logfire_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tools_called: Mapped[list[dict] | None] = mapped_column(JSONB)
    knowledge_retrieval_decisions: Mapped[list[dict] | None] = mapped_column(JSONB)

    agent: Mapped["Agent"] = relationship(back_populates="runs")
    session_messages: Mapped[list["SessionMessage"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    token_usage_steps: Mapped[list["RunTokenUsageStep"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
