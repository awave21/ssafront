from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable name for the API key")
    agent_id: Optional[UUID] = Field(default=None, description="Agent ID to bind the key to (optional)")
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365, description="Days until key expires (1-365)")
    daily_limit: Optional[int] = Field(default=None, ge=1, description="Daily call limit (optional)")
    scopes: Optional[list[str]] = Field(default=None, description="OAuth scopes for the key")


class ApiKeyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    daily_limit: Optional[int] = Field(default=None, ge=1)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    name: str
    last4: str
    scopes: list[str]
    agent_id: Optional[UUID] = None
    expires_at: Optional[datetime] = None
    total_calls: int = 0
    daily_limit: Optional[int] = None
    created_at: datetime
    revoked_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        """Check if the key is active (not revoked and not expired)."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at < datetime.now(timezone.utc):
            return False
        return True


class ApiKeyCreated(ApiKeyRead):
    api_key: str
