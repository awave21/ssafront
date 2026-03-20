"""Dependency for API key-based authentication in integration endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.api_key import ApiKey
from app.db.models.run import Run
from app.db.session import get_db
from app.services.api_keys import hash_api_key


@dataclass
class IntegrationContext:
    """Context for integration API requests (authenticated via API key)."""
    api_key_id: UUID
    tenant_id: UUID
    user_id: UUID
    agent_id: UUID
    scopes: list[str]


async def get_integration_context(
    x_api_key: str = Header(..., description="API key for authentication"),
    db: AsyncSession = Depends(get_db),
) -> IntegrationContext:
    """Validate API key and return integration context.

    Algorithm:
    1. Extract x-api-key from Header
    2. Hash and find ApiKey in DB
    3. Validate:
       - revoked_at is NULL     → 401 "Key revoked"
       - expires_at > now()    → 401 "Key expired"
       - agent_id is NOT NULL  → 400 "Key not bound to agent"
    4. Check daily_limit:
       - COUNT(runs) for today for this agent_id + tenant_id
       - If >= daily_limit → 429 "Daily limit exceeded"
    5. Increment total_calls, update last_used_at
    6. Return IntegrationContext(api_key_id, tenant_id, user_id, agent_id)
    """
    settings = get_settings()
    key_hash = hash_api_key(x_api_key, settings.api_key_pepper)

    # Find the API key
    stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_key", "message": "Invalid API key"},
        )

    # Check if revoked
    if api_key.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "key_revoked", "message": "API key has been revoked"},
        )

    # Check if expired
    if api_key.expires_at is not None and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "key_expired", "message": "API key has expired"},
        )

    # Check if bound to agent
    if api_key.agent_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "key_not_bound", "message": "API key is not bound to an agent"},
        )

    # Check daily limit
    if api_key.daily_limit is not None:
        # Get start of today
        today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)

        # Count runs for this agent today
        stmt = select(func.count()).select_from(Run).where(
            Run.tenant_id == api_key.tenant_id,
            Run.agent_id == api_key.agent_id,
            Run.created_at >= today_start,
        )
        result = await db.execute(stmt)
        today_runs = result.scalar() or 0

        if today_runs >= api_key.daily_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "daily_limit_exceeded",
                    "message": f"Daily limit of {api_key.daily_limit} requests exceeded",
                },
            )

    # Update usage stats
    api_key.total_calls += 1
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    return IntegrationContext(
        api_key_id=api_key.id,
        tenant_id=api_key.tenant_id,
        user_id=api_key.user_id,
        agent_id=api_key.agent_id,
        scopes=api_key.scopes,
    )
