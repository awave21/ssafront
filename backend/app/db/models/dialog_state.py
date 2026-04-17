from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DialogState(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Состояние диалога (сессии) для конкретного агента.

    Позволяет ставить на паузу / отключать агента для конкретного чата,
    не затрагивая остальные диалоги.

    Если записи нет — диалог считается active (обратная совместимость).
    """

    __tablename__ = "dialog_states"
    __table_args__ = (
        UniqueConstraint("session_id", "agent_id", name="uq_dialog_state_session_agent"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), index=True, nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(
        String(200), index=True, nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum("active", "paused", "disabled", name="dialog_status"),
        default="active",
        server_default="active",
        nullable=False,
    )
    last_manager_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_user_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
