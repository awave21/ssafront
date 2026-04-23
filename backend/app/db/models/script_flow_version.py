from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.script_flow import ScriptFlow


class ScriptFlowVersion(Base, UUIDPrimaryKeyMixin):
    """Snapshot of a script flow at publish time (for history / rollback)."""

    __tablename__ = "script_flow_versions"

    flow_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("script_flows.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    flow_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    flow_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    compiled_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    flow: Mapped["ScriptFlow"] = relationship("ScriptFlow", back_populates="version_history")
