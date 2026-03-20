from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DialogTag(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dialog_tags"
    __table_args__ = (
        Index("ix_dialog_tag_agent_session", "agent_id", "session_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    tag: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="rule", server_default="rule", nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    tag_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
