from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin


class ScriptFlowCoverageGapCluster(Base, UUIDPrimaryKeyMixin):
    """A clustered group of low-relevance queries — a "coverage gap topic"
    suggesting an expert should write a new script flow to address it."""

    __tablename__ = "script_flow_coverage_gap_clusters"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_queries: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
