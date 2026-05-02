from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin


class ScriptFlowMissedTacticCall(Base, UUIDPrimaryKeyMixin):
    """User message classified as a tactic-worthy intent (objection / trigger /
    closing / qualification / concern) for which `search_expert_tactics` was
    NOT invoked. Highlights cases where the LLM should have used the tool but
    didn't."""

    __tablename__ = "script_flow_missed_tactic_calls"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
