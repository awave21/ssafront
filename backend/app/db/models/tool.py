from __future__ import annotations

from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.tool_parameter import ToolParameter


class Tool(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tools"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_tool_tenant_name"),)

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    execution_type: Mapped[str] = mapped_column(
        Enum("http_webhook", "internal", name="tool_execution_type"),
        default="http_webhook",
        nullable=False,
    )
    endpoint: Mapped[str | None] = mapped_column(String(500))
    auth_type: Mapped[str] = mapped_column(
        Enum(
            "none",
            "api_key",
            "bearer_token",
            "basic_auth",
            "custom_header",
            "query_param",
            "oauth2",
            "service",
            name="tool_auth_type",
        ),
        default="none",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum("active", "deprecated", name="tool_status"),
        default="active",
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    http_method: Mapped[str] = mapped_column(
        String(10),
        default="POST",
        nullable=False,
        server_default="POST",
    )
    custom_headers: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    response_transform: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    parameter_mapping: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    webhook_scope: Mapped[str] = mapped_column(
        Enum("tool", "function_only", "both", name="tool_webhook_scope"),
        default="tool",
        server_default="tool",
        nullable=False,
    )

    bindings: Mapped[list["AgentToolBinding"]] = relationship(
        back_populates="tool",
        cascade="all, delete-orphan",
    )
    parameters: Mapped[list["ToolParameter"]] = relationship(
        back_populates="tool",
        cascade="all, delete-orphan",
    )
