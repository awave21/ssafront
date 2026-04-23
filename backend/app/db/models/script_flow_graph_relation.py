from __future__ import annotations

from uuid import UUID

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ScriptFlowGraphRelation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "script_flow_graph_relations"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    flow_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("script_flows.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    flow_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source_graph_node_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_graph_node_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1")
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
