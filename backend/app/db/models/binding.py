from __future__ import annotations

from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.agent import Agent
    from app.db.models.credential import Credential
    from app.db.models.tool import Tool


class AgentToolBinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_tool_bindings"
    __table_args__ = (UniqueConstraint("agent_id", "tool_id", name="uq_agent_tool"),)

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tool_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tools.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    credential_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("credentials.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    permission_scope: Mapped[str] = mapped_column(
        Enum("read", "write", name="binding_permission_scope"),
        default="read",
        nullable=False,
    )
    timeout_ms: Mapped[int | None] = mapped_column(Integer)
    rate_limit: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    allowed_domains: Mapped[list[str] | None] = mapped_column(JSONB)
    secrets_ref: Mapped[str | None] = mapped_column(nullable=True)

    agent: Mapped["Agent"] = relationship(back_populates="bindings")
    tool: Mapped["Tool"] = relationship(back_populates="bindings")
    credential: Mapped["Credential | None"] = relationship()