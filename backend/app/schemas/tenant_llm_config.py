from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TenantLLMConfigSet(BaseModel):
    """Payload for setting the OpenAI API key."""
    api_key: str = Field(..., min_length=10, max_length=512, description="OpenAI API key (sk-...)")
    provider: str = Field(default="openai", pattern=r"^[a-z0-9_-]+$", max_length=50)


class TenantLLMConfigRead(BaseModel):
    id: UUID
    tenant_id: UUID
    provider: str
    last4: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TenantLLMConfigStatus(BaseModel):
    """Lightweight check: does the tenant have a key configured?"""
    has_key: bool
    provider: str = "openai"
    last4: str | None = None
    is_active: bool = False
