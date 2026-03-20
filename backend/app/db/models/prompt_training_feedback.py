from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PromptTrainingFeedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Одна коррекция / оценка в рамках тренировочной сессии."""

    __tablename__ = "prompt_training_feedback"

    training_session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("prompt_training_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        index=True,
        nullable=False,
    )
    run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    feedback_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )
    user_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_text: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    training_session: Mapped["PromptTrainingSession"] = relationship(
        "PromptTrainingSession",
        back_populates="feedbacks",
    )
