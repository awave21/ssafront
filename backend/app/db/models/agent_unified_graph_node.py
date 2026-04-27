from __future__ import annotations

from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AgentUnifiedGraphNode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Узел единого графа агента (SQNS, структура БЗ, в будущем — LLM-триплеты).

    Сценарный GraphRAG остаётся в ``script_flow_graph_*``; здесь — сквозной слой
    для связей «таблицы + файлы + справочники» и последующего GraphRAG по тексту.
    """

    __tablename__ = "agent_unified_graph_nodes"
    __table_args__ = (
        UniqueConstraint("agent_id", "graph_node_id", name="uq_agent_unified_graph_nodes_agent_graph_node_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    origin_slice: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    graph_node_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain_entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    provenance_tier: Mapped[str] = mapped_column(String(16), nullable=False, server_default="gold")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    embedding_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
