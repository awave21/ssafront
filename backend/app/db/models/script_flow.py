from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.agent import Agent
    from app.db.models.script_flow_version import ScriptFlowVersion
    from app.db.models.script_node import ScriptNode


class ScriptFlow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "script_flows"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    flow_status: Mapped[str] = mapped_column(
        Enum("draft", "published", name="script_flow_status"),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    published_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    indexed_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    definition_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    flow_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    flow_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    compiled_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    index_status: Mapped[str] = mapped_column(
        Enum("idle", "pending", "indexing", "indexed", "failed", name="script_flow_index_status"),
        nullable=False,
        default="idle",
        server_default="idle",
    )
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    index_progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    index_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    index_cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    agent: Mapped["Agent"] = relationship("Agent", back_populates="script_flows")
    nodes: Mapped[list["ScriptNode"]] = relationship(
        "ScriptNode", back_populates="flow", cascade="all, delete-orphan"
    )
    version_history: Mapped[list["ScriptFlowVersion"]] = relationship(
        "ScriptFlowVersion",
        back_populates="flow",
        cascade="all, delete-orphan",
    )
