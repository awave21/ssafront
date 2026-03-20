from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.agent import Agent


class DirectQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "direct_questions"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    search_title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    interrupt_dialog: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_telegram: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    followup: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    embedding_status: Mapped[str] = mapped_column(
        Enum("ready", "pending", "failed", name="direct_question_embedding_status"),
        default="ready",
        nullable=False,
    )
    embedding_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    embedding_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="direct_questions")
    files: Mapped[list["DirectQuestionFile"]] = relationship(
        "DirectQuestionFile",
        back_populates="direct_question",
        cascade="all, delete-orphan",
        order_by="DirectQuestionFile.sort_order.asc()",
    )


class DirectQuestionFile(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "direct_question_files"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    direct_question_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("direct_questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    direct_question: Mapped["DirectQuestion"] = relationship("DirectQuestion", back_populates="files")
