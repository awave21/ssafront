from __future__ import annotations

from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ScriptFlowNodeIndex(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "script_flow_node_indexes"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    flow_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("script_flows.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    flow_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    node_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    stage: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    service_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    employee_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    motive_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    objection_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    proof_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    constraint_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    required_followup_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    communication_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_phrases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    forbidden_phrases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    is_searchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

