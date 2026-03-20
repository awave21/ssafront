from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentUserStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: UUID
    platform: str
    platform_user_id: str
    is_disabled: bool
    disabled_at: datetime | None = None
    disabled_by_user_id: UUID | None = None


class AgentUserStateUpdate(BaseModel):
    is_disabled: bool = Field(..., description="Отключить агента для конкретного пользователя")
