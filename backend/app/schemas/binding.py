from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BindingBase(BaseModel):
    permission_scope: Literal["read", "write"] = "read"
    timeout_ms: int | None = Field(default=None, ge=1000, le=60000)
    rate_limit: dict[str, Any] | None = None
    allowed_domains: list[str] | None = None
    secrets_ref: str | None = None
    credential_id: UUID | None = None


class BindingCreate(BindingBase):
    pass


class BindingRead(BindingBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    tool_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class BindingWithToolRead(BindingRead):
    """Binding с полной информацией о tool."""

    tool: "ToolWithParametersRead | None" = None


# Resolve forward references after all types are importable
from app.schemas.tool import ToolRead  # noqa: E402
from app.schemas.tool_parameter import ToolParameterRead  # noqa: E402


class ToolWithParametersRead(ToolRead):
    parameters: list[ToolParameterRead] = Field(default_factory=list)

BindingWithToolRead.model_rebuild()
