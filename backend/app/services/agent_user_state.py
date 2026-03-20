from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_user_state import AgentUserState


def normalize_identity(platform: str, platform_user_id: str) -> tuple[str, str]:
    norm_platform = platform.strip().lower()
    norm_user_id = platform_user_id.strip()

    # Поддержка frontend-формата dialogId (например, "telegram:306597938")
    # в поле platform_user_id для обратной совместимости.
    if ":" in norm_user_id:
        prefix, suffix = norm_user_id.split(":", 1)
        prefix = prefix.strip().lower()
        suffix = suffix.strip()
        if prefix and suffix and prefix == norm_platform:
            norm_user_id = suffix

    return norm_platform, norm_user_id


async def get_agent_user_state(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    platform: str,
    platform_user_id: str,
) -> AgentUserState | None:
    norm_platform, norm_user_id = normalize_identity(platform, platform_user_id)
    stmt = select(AgentUserState).where(
        AgentUserState.tenant_id == tenant_id,
        AgentUserState.agent_id == agent_id,
        AgentUserState.platform == norm_platform,
        AgentUserState.platform_user_id == norm_user_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def is_agent_user_disabled(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    platform: str,
    platform_user_id: str,
) -> bool:
    state = await get_agent_user_state(
        db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        platform=platform,
        platform_user_id=platform_user_id,
    )
    return bool(state and state.is_disabled)


async def is_agent_user_disabled_by_session(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    session_id: str,
) -> bool:
    if not session_id or ":" not in session_id:
        return False
    platform, platform_user_id = session_id.split(":", 1)
    if not platform or not platform_user_id:
        return False
    return await is_agent_user_disabled(
        db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        platform=platform,
        platform_user_id=platform_user_id,
    )


async def upsert_agent_user_state(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    platform: str,
    platform_user_id: str,
    is_disabled: bool,
    changed_by_user_id: UUID,
) -> tuple[AgentUserState, bool]:
    state = await get_agent_user_state(
        db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        platform=platform,
        platform_user_id=platform_user_id,
    )
    previous = bool(state and state.is_disabled)

    norm_platform, norm_user_id = normalize_identity(platform, platform_user_id)
    if state is None:
        state = AgentUserState(
            tenant_id=tenant_id,
            agent_id=agent_id,
            platform=norm_platform,
            platform_user_id=norm_user_id,
        )
        db.add(state)

    state.is_disabled = is_disabled
    if is_disabled:
        state.disabled_at = datetime.now(timezone.utc)
        state.disabled_by_user_id = changed_by_user_id
    else:
        state.disabled_at = None
        state.disabled_by_user_id = None

    await db.commit()
    await db.refresh(state)
    return state, previous
