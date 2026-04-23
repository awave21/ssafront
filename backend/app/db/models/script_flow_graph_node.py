from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ScriptFlowGraphNode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "script_flow_graph_nodes"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    flow_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("script_flows.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    flow_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    graph_node_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    node_kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_node_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    community_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
