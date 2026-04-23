from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ScriptFlowEdgeIndex(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "script_flow_edge_indexes"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    flow_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("script_flows.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_node_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    target_node_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    source_handle: Mapped[str | None] = mapped_column(String(120), nullable=True)
    branch_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

