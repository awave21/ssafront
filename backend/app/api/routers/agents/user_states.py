from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.db.session import get_db
from app.schemas.agent_user_state import AgentUserStateRead, AgentUserStateUpdate
from app.schemas.auth import AuthContext
from app.services.dialog_state import set_dialog_status
from app.services.agent_user_state import get_agent_user_state, upsert_agent_user_state
from app.services.audit import write_audit

router = APIRouter()


@router.get("/users/{platform}/{platform_user_id}/state", response_model=AgentUserStateRead)
async def get_user_state(
    agent_id: UUID,
    platform: str,
    platform_user_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> AgentUserStateRead:
    await get_agent_or_404(agent_id, db, user)
    state = await get_agent_user_state(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        platform=platform,
        platform_user_id=platform_user_id,
    )
    if state is None:
        return AgentUserStateRead(
            agent_id=agent_id,
            platform=platform.strip().lower(),
            platform_user_id=platform_user_id.strip(),
            is_disabled=False,
            disabled_at=None,
            disabled_by_user_id=None,
        )
    return AgentUserStateRead.model_validate(state)


@router.put("/users/{platform}/{platform_user_id}/state", response_model=AgentUserStateRead)
async def set_user_state(
    agent_id: UUID,
    platform: str,
    platform_user_id: str,
    payload: AgentUserStateUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> AgentUserStateRead:
    await get_agent_or_404(agent_id, db, user)
    state, old_value = await upsert_agent_user_state(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        platform=platform,
        platform_user_id=platform_user_id,
        is_disabled=payload.is_disabled,
        changed_by_user_id=user.user_id,
    )

    # Синхронизируем legacy dialog_status для Telegram, чтобы не было конфликта
    # между старой per-dialog блокировкой и новым per-user переключателем.
    if state.platform == "telegram":
        session_id = f"telegram:{state.platform_user_id}"
        await set_dialog_status(
            db,
            agent_id=agent_id,
            tenant_id=user.tenant_id,
            session_id=session_id,
            new_status="disabled" if state.is_disabled else "active",
        )

    await write_audit(
        db,
        user,
        "agent.user.disable.toggle",
        "agent",
        str(agent_id),
        metadata={
            "platform": state.platform,
            "platform_user_id": state.platform_user_id,
            "old_value": old_value,
            "new_value": state.is_disabled,
        },
    )
    return AgentUserStateRead.model_validate(state)
