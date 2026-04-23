from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ScriptFlowGraphDiagnostic(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "script_flow_graph_diagnostics"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    flow_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("script_flows.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    flow_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    extraction_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    summary_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    extraction_mode: Mapped[str | None] = mapped_column(String(60), nullable=True)
    llm_ok_nodes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    llm_failed_nodes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    entity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    relation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    community_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    summary_llm_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    summary_fallback_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    debug: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

