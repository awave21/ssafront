from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


AuthType = Literal[
    "none",
    "api_key",
    "bearer_token",
    "basic_auth",
    "custom_header",
    "query_param",
    "oauth2",
    "service",
]


class CredentialBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    auth_type: AuthType
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class CredentialCreate(CredentialBase):
    pass


class CredentialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    auth_type: AuthType | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class CredentialRead(CredentialBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class CredentialTestRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2000)
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    headers: dict[str, str] | None = None
    params: dict[str, Any] | None = None
    json: dict[str, Any] | None = None
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    allowed_domains: list[str] | None = None


class CredentialTestResponse(BaseModel):
    status_code: int
    body: str
