"""Эндпоинты для истории версий системного промпта агента."""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.system_prompt_version import (
    SystemPromptVersionCreate,
    SystemPromptVersionListItem,
    SystemPromptVersionListResponse,
    SystemPromptVersionRead,
)
from app.services.audit import write_audit
from app.services.system_prompt_history import (
    activate_version,
    create_version,
    get_active_version,
    get_version_by_id,
    list_versions,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get(
    "/system-prompt/history",
    response_model=SystemPromptVersionListResponse,
    summary="Список версий системного промпта",
)
async def list_prompt_versions(
    agent_id: UUID,
    limit: int = Query(default=30, ge=1, le=100, description="Количество записей"),
    cursor: int | None = Query(default=None, description="version_number последнего загруженного элемента"),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> SystemPromptVersionListResponse:
    agent = await get_agent_or_404(agent_id, db, user)
    versions = await list_versions(
        db, agent.id, agent.tenant_id, limit=limit + 1, cursor_version=cursor,
    )

    has_more = len(versions) > limit
    if has_more:
        versions = versions[:limit]

    items = [
        SystemPromptVersionListItem(
            id=v.id,
            agent_id=v.agent_id,
            version_number=v.version_number,
            change_summary=v.change_summary,
            triggered_by=v.triggered_by,
            is_active=v.is_active,
            created_by=v.created_by,
            created_at=v.created_at,
            prompt_length=len(v.system_prompt) if v.system_prompt else 0,
        )
        for v in versions
    ]

    next_cursor = items[-1].version_number if has_more and items else None

    return SystemPromptVersionListResponse(items=items, next_cursor=next_cursor)


@router.get(
    "/system-prompt/current",
    response_model=SystemPromptVersionRead,
    summary="Текущая активная версия системного промпта",
)
async def get_current_prompt_version(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> SystemPromptVersionRead:
    agent = await get_agent_or_404(agent_id, db, user)
    version = await get_active_version(db, agent.id, agent.tenant_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active system prompt version found",
        )
    return SystemPromptVersionRead.model_validate(version)


@router.get(
    "/system-prompt/history/{version_id}",
    response_model=SystemPromptVersionRead,
    summary="Детали конкретной версии промпта",
)
async def get_prompt_version_detail(
    agent_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> SystemPromptVersionRead:
    agent = await get_agent_or_404(agent_id, db, user)
    version = await get_version_by_id(db, version_id, agent.id, agent.tenant_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt version not found",
        )
    return SystemPromptVersionRead.model_validate(version)


@router.post(
    "/system-prompt/history",
    response_model=SystemPromptVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую версию системного промпта",
)
async def create_prompt_version(
    agent_id: UUID,
    payload: SystemPromptVersionCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> SystemPromptVersionRead:
    agent = await get_agent_or_404(agent_id, db, user)

    version = await create_version(
        db,
        agent,
        system_prompt=payload.system_prompt,
        user=user,
        change_summary=payload.change_summary,
        triggered_by="manual",
        activate=payload.activate,
    )

    await db.commit()
    await db.refresh(version)

    await write_audit(
        db,
        user,
        "agent.system_prompt.create_version",
        "system_prompt_version",
        str(version.id),
        metadata={
            "agent_id": str(agent.id),
            "version_number": version.version_number,
            "activated": payload.activate,
        },
    )

    logger.info(
        "prompt_version_created_via_api",
        agent_id=str(agent.id),
        version_id=str(version.id),
        version_number=version.version_number,
    )

    return SystemPromptVersionRead.model_validate(version)


@router.post(
    "/system-prompt/history/{version_id}/activate",
    response_model=SystemPromptVersionRead,
    summary="Активировать выбранную версию промпта",
)
async def activate_prompt_version(
    agent_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> SystemPromptVersionRead:
    agent = await get_agent_or_404(agent_id, db, user)
    version = await get_version_by_id(db, version_id, agent.id, agent.tenant_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt version not found",
        )

    if version.is_active:
        return SystemPromptVersionRead.model_validate(version)

    version = await activate_version(db, version, agent)

    await db.commit()
    await db.refresh(version)

    await write_audit(
        db,
        user,
        "agent.system_prompt.activate_version",
        "system_prompt_version",
        str(version.id),
        metadata={
            "agent_id": str(agent.id),
            "version_number": version.version_number,
        },
    )

    logger.info(
        "prompt_version_activated_via_api",
        agent_id=str(agent.id),
        version_id=str(version.id),
        version_number=version.version_number,
    )

    return SystemPromptVersionRead.model_validate(version)
