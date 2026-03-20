from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_or_404, require_scope
from app.core.config import get_settings
from app.db.models.api_key import ApiKey
from app.db.models.agent import Agent
from app.db.models.run import Run
from app.db.session import get_db
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead, ApiKeyUpdate
from app.schemas.auth import AuthContext
from app.services.api_keys import generate_api_key, hash_api_key

router = APIRouter()

# Default scopes for integration keys
INTEGRATION_SCOPES = ["runs:write", "dialogs:read"]


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("settings:write")),
) -> ApiKeyCreated:
    # Validate agent_id if provided
    agent_id = payload.agent_id
    if agent_id:
        # Check agent exists, belongs to tenant, and is not deleted
        agent = await get_or_404(
            db, Agent,
            id=agent_id,
            tenant_id=user.tenant_id,
            label="Agent",
            extra_where=[Agent.deleted_at.is_(None)],
        )

    # Determine scopes: use provided or defaults for integration keys
    if payload.scopes:
        requested_scopes = payload.scopes
        if any(scope not in user.scopes for scope in requested_scopes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid scopes")
    elif agent_id:
        # Auto-assign integration scopes for keys bound to an agent
        requested_scopes = INTEGRATION_SCOPES
    else:
        requested_scopes = user.scopes

    # Calculate expires_at from expires_in_days
    expires_at = None
    if payload.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)

    raw_key = generate_api_key()
    settings = get_settings()
    key_hash = hash_api_key(raw_key, settings.api_key_pepper)

    api_key = ApiKey(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        key_hash=key_hash,
        last4=raw_key[-4:],
        scopes=requested_scopes,
        name=payload.name,
        agent_id=agent_id,
        expires_at=expires_at,
        daily_limit=payload.daily_limit,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    data = ApiKeyRead.model_validate(api_key).model_dump()
    data["api_key"] = raw_key
    return ApiKeyCreated(**data)


@router.get("", response_model=list[ApiKeyRead])
async def list_api_keys(
    agent_id: UUID | None = Query(default=None, description="Filter by agent ID"),
    include_revoked: bool = False,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("settings:write")),
) -> list[ApiKeyRead]:
    stmt = select(ApiKey).where(
        ApiKey.tenant_id == user.tenant_id,
        ApiKey.user_id == user.user_id,
    )
    if agent_id:
        stmt = stmt.where(ApiKey.agent_id == agent_id)
    if not include_revoked:
        stmt = stmt.where(ApiKey.revoked_at.is_(None))
    result = await db.execute(stmt.order_by(ApiKey.created_at.desc()))
    keys = result.scalars().all()
    return [ApiKeyRead.model_validate(key) for key in keys]


@router.patch("/{api_key_id}", response_model=ApiKeyRead)
async def update_api_key(
    api_key_id: UUID,
    payload: ApiKeyUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("settings:write")),
) -> ApiKeyRead:
    # Get the API key
    api_key = await get_or_404(
        db, ApiKey,
        id=api_key_id,
        tenant_id=user.tenant_id,
        label="API Key",
    )

    # Update fields if provided
    if payload.name is not None:
        api_key.name = payload.name
    if payload.daily_limit is not None:
        api_key.daily_limit = payload.daily_limit
    if payload.expires_in_days is not None:
        if payload.expires_in_days > 0:
            api_key.expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
        else:
            api_key.expires_at = None

    await db.commit()
    await db.refresh(api_key)
    return ApiKeyRead.model_validate(api_key)


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("settings:write")),
) -> None:
    stmt = select(ApiKey).where(
        ApiKey.id == api_key_id,
        ApiKey.tenant_id == user.tenant_id,
        ApiKey.user_id == user.user_id,
    )
    api_key = (await db.execute(stmt)).scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    api_key.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return None
