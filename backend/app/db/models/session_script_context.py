from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin


class SessionScriptContext(Base, UUIDPrimaryKeyMixin):
    """
    Tracks expert-script navigation state per agent session.

    One row per (agent_id, session_id) pair.  The row is upserted on every
    navigate_script call so the runtime always has fresh context without
    loading the full message history.
    """

    __tablename__ = "session_script_contexts"

    agent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), index=True, unique=True, nullable=False
    )

    # Free-text topics already discussed, e.g. ["price", "comparison"]
    topics_discussed: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    # How many times each topic was addressed, e.g. {"price": 2, "time": 1}
    objection_attempts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # Resolved service/employee from earlier in the conversation
    detected_service_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    detected_employee_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    # node_ref_id of the last ScriptNode returned to the LLM — used for
    # contextual traversal: next call first checks this node's next_steps
    current_node_ref_id: Mapped[str | None] = mapped_column(
        nullable=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
