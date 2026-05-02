from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin


class ScriptFlowTacticSearch(Base, UUIDPrimaryKeyMixin):
    """One row per `search_expert_tactics` invocation by the runtime LLM.

    Used to compute coverage analytics: which tactics get hit, which queries
    return low-scoring (mismatched) results, and where the expert needs to
    write new scenarios.
    """

    __tablename__ = "script_flow_tactic_searches"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    query: Mapped[str] = mapped_column(Text, nullable=False)
    service_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    top_node_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    top_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    top_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    search_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Stage 3: post-run scoring of tactic application
    run_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    violation: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    followup_asked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    agent_response_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
