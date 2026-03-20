from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.tenant import TenantRead
from app.schemas.user import UserRead


class TokenPayload(BaseModel):
    user_id: UUID = Field(alias="sub")
    tenant_id: UUID
    role: str = Field(default="manager")
    scopes: list[str] = Field(default_factory=list)


class AuthContext(BaseModel):
    user_id: UUID
    tenant_id: UUID
    role: str = "system"  # Default for webhooks/internal calls
    scopes: list[str] = Field(default_factory=list)


Scope = Annotated[str, Field(min_length=1)]


class TokenResponse(BaseModel):
    token: str
    refresh_token: str | None = None


class AuthTokenResponse(TokenResponse):
    user: UserRead
    tenant: TenantRead


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutResponse(BaseModel):
    success: bool = True
