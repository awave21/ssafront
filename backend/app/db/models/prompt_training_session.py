from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PromptTrainingSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Сессия обучения промпта — пользователь даёт коррекции, мета-агент генерирует улучшенный system prompt."""

    __tablename__ = "prompt_training_sessions"

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        index=True,
        nullable=False,
    )
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
    )
    base_prompt_version: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )
    generated_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_prompt_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("system_prompt_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    feedback_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    meta_model: Mapped[str] = mapped_column(
        String(200), nullable=False, default="openai:gpt-4.1",
    )

    feedbacks: Mapped[list["PromptTrainingFeedback"]] = relationship(
        "PromptTrainingFeedback",
        back_populates="training_session",
        cascade="all, delete-orphan",
        order_by="PromptTrainingFeedback.order_index",
    )
