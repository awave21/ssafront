from __future__ import annotations

from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.tool import Tool


class ToolParameter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tool_parameters"
    __table_args__ = (
        UniqueConstraint("tool_id", "name", name="uq_tool_parameter_tool_name"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    tool_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tools.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(
        Enum("text", "number", "boolean", name="tool_parameter_type"),
        nullable=False,
    )
    instruction: Mapped[str] = mapped_column(String(500), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    enum_values: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    x_from_ai: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    default_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    tool: Mapped["Tool"] = relationship(back_populates="parameters")
