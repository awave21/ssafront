from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class InvitationAccept(BaseModel):
    token: str | None = Field(default=None, description="Invite token from URL")
    invite_token: str | None = Field(default=None, description="Alias for token")
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def resolve_token(self) -> "InvitationAccept":
        if not self.token and not self.invite_token:
            raise ValueError("Either token or invite_token is required")
        if not self.token:
            object.__setattr__(self, "token", self.invite_token or "")
        return self


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(..., pattern="^(admin|manager)$")


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    email: str
    role: str
    expires_at: datetime
    invited_by_user_id: UUID
    created_at: datetime


class InvitationCreated(InvitationRead):
    invite_link: str


class InvitationListItem(InvitationRead):
    """Invitation item with optional invite_link (may be null for legacy invitations)."""
    invite_link: str | None = None


class ExistingInvitation(BaseModel):
    """Existing invitation info returned on 409 conflict."""
    id: UUID
    email: str
    invite_link: str | None = None
    expires_at: datetime


class InvitationConflictResponse(BaseModel):
    """Response body for 409 Conflict when invitation already exists."""
    error: str
    existing_invitation: ExistingInvitation
