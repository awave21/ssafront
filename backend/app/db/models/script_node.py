from __future__ import annotations

from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.script_flow import ScriptFlow


class ScriptNode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "script_nodes"

    flow_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("script_flows.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)

    node_ref_id: Mapped[str] = mapped_column(String(200), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="expertise")
    stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    service_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    employee_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")

    situation: Mapped[str] = mapped_column(Text, nullable=False, server_default="''")
    why_it_works: Mapped[str | None] = mapped_column(Text, nullable=True)
    approach: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_phrases: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    watch_out: Mapped[str | None] = mapped_column(Text, nullable=True)
    good_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_steps: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")

    is_entry_point: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    outcome_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    final_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    flow: Mapped["ScriptFlow"] = relationship("ScriptFlow", back_populates="nodes")
