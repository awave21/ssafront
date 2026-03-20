from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SessionMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "session_messages"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_index: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    run: Mapped["Run"] = relationship(back_populates="session_messages")
