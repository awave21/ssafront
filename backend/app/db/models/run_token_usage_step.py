from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.run import Run


class RunTokenUsageStep(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "run_token_usage_steps"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(200), index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    input_cached_tokens: Mapped[int | None] = mapped_column(Integer)
    input_non_cached_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    audio_tokens: Mapped[int | None] = mapped_column(Integer)
    input_audio_tokens: Mapped[int | None] = mapped_column(Integer)
    output_audio_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_audio_read_tokens: Mapped[int | None] = mapped_column(Integer)
    accepted_prediction_tokens: Mapped[int | None] = mapped_column(Integer)
    rejected_prediction_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    cost_rub: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    cost_usd_logfire: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))

    run: Mapped["Run"] = relationship(back_populates="token_usage_steps")
