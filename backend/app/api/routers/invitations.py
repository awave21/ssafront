from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.api.deps import get_current_user, get_or_404, require_scope
from app.core.config import get_settings
from app.services.invitations import get_invitation_by_token, hash_invite_token
from app.db.models.invitation import Invitation
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import AuthContext, AuthTokenResponse
from app.schemas.invitation import (
    InvitationAccept,
    InvitationConflictResponse,
    InvitationCreate,
    InvitationCreated,
    InvitationListItem,
    InvitationRead,
    ExistingInvitation,
)
from app.schemas.tenant import TenantRead
from app.schemas.user import UserRead
from app.services.passwords import hash_password
from app.services.users import normalize_email, resolve_scopes

from app.api.routers.auth.utils import _create_error_response, _create_refresh_token, _issue_token

logger = structlog.get_logger()

router = APIRouter()

INVITE_TOKEN_EXPIRY_DAYS = 7


@router.post(
    "",
    response_model=InvitationCreated,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": InvitationConflictResponse}},
)
async def create_invitation(
    payload: InvitationCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_scope("members:manage")),
) -> InvitationCreated:
    settings = get_settings()
    normalized_email = normalize_email(payload.email)

    existing_user = (await db.execute(select(User).where(User.email == normalized_email))).scalar_one_or_none()
    if existing_user and existing_user.tenant_id == auth.tenant_id:
        raise _create_error_response(
            "user_exists",
            "Пользователь с таким email уже в организации",
            status.HTTP_409_CONFLICT,
        )

    # Check for existing invitation first
    existing_invitation = (
        await db.execute(
            select(Invitation).where(
                Invitation.tenant_id == auth.tenant_id,
                Invitation.email == normalized_email,
                Invitation.expires_at > datetime.now(timezone.utc),
            )
        )
    ).scalar_one_or_none()

    if existing_invitation:
        # Return existing invitation info on conflict
        invite_base = settings.get_invite_link_base().rstrip("/")
        invite_link = f"{invite_base}/invite/accept?token={existing_invitation.token}" if existing_invitation.token else None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Invitation already exists",
                "existing_invitation": {
                    "id": str(existing_invitation.id),
                    "email": existing_invitation.email,
                    "invite_link": invite_link,
                    "expires_at": existing_invitation.expires_at.isoformat(),
                },
            },
        )

    token = secrets.token_urlsafe(32)
    token_hash = hash_invite_token(token, settings.jwt_secret)
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TOKEN_EXPIRY_DAYS)

    invitation = Invitation(
        tenant_id=auth.tenant_id,
        email=normalized_email,
        role=payload.role,
        token_hash=token_hash,
        token=token,  # Store plain token for invite_link retrieval
        expires_at=expires_at,
        invited_by_user_id=auth.user_id,
    )
    db.add(invitation)
    try:
        await db.commit()
        await db.refresh(invitation)
    except IntegrityError:
        await db.rollback()
        raise _create_error_response(
            "invitation_exists",
            "Активное приглашение для этого email уже существует",
            status.HTTP_409_CONFLICT,
        )

    invite_base = settings.get_invite_link_base().rstrip("/")
    invite_link = f"{invite_base}/invite/accept?token={token}"

    return InvitationCreated(
        id=invitation.id,
        tenant_id=invitation.tenant_id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        invited_by_user_id=invitation.invited_by_user_id,
        created_at=invitation.created_at,
        invite_link=invite_link,
    )


@router.get("", response_model=list[InvitationListItem])
async def list_invitations(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_scope("members:manage")),
) -> list[InvitationListItem]:
    """
    Get list of pending invitations for current tenant.
    Only for users with members:manage scope (owner/admin).
    """
    settings = get_settings()
    invite_base = settings.get_invite_link_base().rstrip("/")

    stmt = (
        select(Invitation)
        .where(
            Invitation.tenant_id == auth.tenant_id,
            Invitation.expires_at > datetime.now(timezone.utc),
        )
        .order_by(Invitation.created_at.desc())
    )
    result = await db.execute(stmt)
    invitations = result.scalars().all()

    items = []
    for inv in invitations:
        invite_link = f"{invite_base}/invite/accept?token={inv.token}" if inv.token else None
        items.append(
            InvitationListItem(
                id=inv.id,
                tenant_id=inv.tenant_id,
                email=inv.email,
                role=inv.role,
                expires_at=inv.expires_at,
                invited_by_user_id=inv.invited_by_user_id,
                created_at=inv.created_at,
                invite_link=invite_link,
            )
        )
    return items


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invitation(
    invitation_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_scope("members:manage")),
) -> None:
    """
    Cancel/delete an invitation.
    Only for users with members:manage scope (owner/admin).

    Returns:
        204 No Content - successfully deleted
        404 Not Found - invitation not found or belongs to different tenant
        403 Forbidden - insufficient permissions
    """
    invitation = await get_or_404(db, Invitation, id=invitation_id, tenant_id=auth.tenant_id, label="Invitation")
    await db.delete(invitation)
    await db.commit()
    return None


@router.post("/accept", response_model=AuthTokenResponse)
async def accept_invitation(
    payload: InvitationAccept,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    """Публичный эндпоинт: принять приглашение по token."""
    token = payload.token
    password = payload.password
    full_name = payload.full_name

    if not token or not password:
        raise _create_error_response(
            "invalid_request",
            "Требуются token и password",
            status.HTTP_400_BAD_REQUEST,
        )

    invitation = await get_invitation_by_token(db, token, get_settings().jwt_secret)
    if not invitation:
        raise _create_error_response(
            "invalid_or_expired_token",
            "Ссылка приглашения недействительна или истекла",
            status.HTTP_400_BAD_REQUEST,
        )

    normalized_email = normalize_email(invitation.email)
    existing_user = (await db.execute(select(User).where(User.email == normalized_email))).scalar_one_or_none()
    if existing_user:
        raise _create_error_response(
            "user_exists",
            "Пользователь с таким email уже зарегистрирован",
            status.HTTP_409_CONFLICT,
        )

    user = User(
        tenant_id=invitation.tenant_id,
        email=normalized_email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=invitation.role,
        scopes=resolve_scopes(invitation.role, None),
        is_active=True,
    )
    db.add(user)
    await db.delete(invitation)
    await db.commit()
    await db.refresh(user)

    tenant = await db.get(Tenant, invitation.tenant_id)
    if not tenant:
        raise _create_error_response("internal_error", "Tenant not found", status.HTTP_500_INTERNAL_SERVER_ERROR)

    settings = get_settings()
    jwt_token = _issue_token(settings, str(user.id), str(user.tenant_id), user.scopes, user.role)
    refresh_token = await _create_refresh_token(db, settings, str(user.id))

    return AuthTokenResponse(
        token=jwt_token,
        refresh_token=refresh_token,
        user=UserRead.model_validate(user),
        tenant=TenantRead.model_validate(tenant),
    )
