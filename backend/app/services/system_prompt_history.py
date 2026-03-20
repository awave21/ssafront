"""Сервис для управления историей версий системного промпта агента."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.system_prompt_version import SystemPromptVersion
from app.schemas.auth import AuthContext

logger = structlog.get_logger(__name__)


async def get_next_version_number(db: AsyncSession, agent_id: UUID) -> int:
    """Получить следующий номер версии для агента."""
    stmt = (
        select(func.coalesce(func.max(SystemPromptVersion.version_number), 0))
        .where(SystemPromptVersion.agent_id == agent_id)
    )
    result = await db.execute(stmt)
    current_max = result.scalar_one()
    return current_max + 1


async def create_version(
    db: AsyncSession,
    agent: Agent,
    *,
    system_prompt: str,
    user: AuthContext,
    change_summary: str | None = None,
    triggered_by: str = "manual",
    activate: bool = True,
) -> SystemPromptVersion:
    """
    Создать новую версию системного промпта.

    Если activate=True — деактивирует все предыдущие версии и обновляет agent.system_prompt.
    """
    version_number = await get_next_version_number(db, agent.id)

    if activate:
        # Деактивировать все предыдущие версии
        await db.execute(
            update(SystemPromptVersion)
            .where(
                SystemPromptVersion.agent_id == agent.id,
                SystemPromptVersion.is_active.is_(True),
            )
            .values(is_active=False)
        )

    version = SystemPromptVersion(
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        version_number=version_number,
        system_prompt=system_prompt,
        change_summary=change_summary,
        triggered_by=triggered_by,
        is_active=activate,
        created_by=user.user_id,
    )
    db.add(version)

    if activate:
        agent.system_prompt = system_prompt
        agent.version = version_number

    await db.flush()

    logger.info(
        "system_prompt_version_created",
        agent_id=str(agent.id),
        version_number=version_number,
        triggered_by=triggered_by,
        is_active=activate,
        prompt_length=len(system_prompt),
    )

    return version


async def list_versions(
    db: AsyncSession,
    agent_id: UUID,
    tenant_id: UUID,
    *,
    limit: int = 30,
    cursor_version: int | None = None,
) -> list[SystemPromptVersion]:
    """
    Вернуть версии промпта для агента (от новой к старой).

    cursor_version — version_number последнего загруженного элемента.
    Следующая порция начнётся со строк, у которых version_number < cursor_version.
    """
    stmt = (
        select(SystemPromptVersion)
        .where(
            SystemPromptVersion.agent_id == agent_id,
            SystemPromptVersion.tenant_id == tenant_id,
        )
    )
    if cursor_version is not None:
        stmt = stmt.where(SystemPromptVersion.version_number < cursor_version)

    stmt = stmt.order_by(SystemPromptVersion.version_number.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_version_by_id(
    db: AsyncSession,
    version_id: UUID,
    agent_id: UUID,
    tenant_id: UUID,
) -> SystemPromptVersion | None:
    """Получить конкретную версию по id."""
    stmt = select(SystemPromptVersion).where(
        SystemPromptVersion.id == version_id,
        SystemPromptVersion.agent_id == agent_id,
        SystemPromptVersion.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_version(
    db: AsyncSession,
    agent_id: UUID,
    tenant_id: UUID,
) -> SystemPromptVersion | None:
    """Получить текущую активную версию промпта."""
    stmt = select(SystemPromptVersion).where(
        SystemPromptVersion.agent_id == agent_id,
        SystemPromptVersion.tenant_id == tenant_id,
        SystemPromptVersion.is_active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def activate_version(
    db: AsyncSession,
    version: SystemPromptVersion,
    agent: Agent,
) -> SystemPromptVersion:
    """Сделать указанную версию активной, деактивировать остальные."""
    # Деактивировать все
    await db.execute(
        update(SystemPromptVersion)
        .where(
            SystemPromptVersion.agent_id == agent.id,
            SystemPromptVersion.is_active.is_(True),
        )
        .values(is_active=False)
    )

    # Активировать выбранную
    version.is_active = True
    agent.system_prompt = version.system_prompt
    agent.version = version.version_number

    await db.flush()

    logger.info(
        "system_prompt_version_activated",
        agent_id=str(agent.id),
        version_id=str(version.id),
        version_number=version.version_number,
    )

    return version


async def count_versions(
    db: AsyncSession,
    agent_id: UUID,
    tenant_id: UUID,
) -> int:
    """Подсчитать количество версий для агента."""
    stmt = (
        select(func.count())
        .select_from(SystemPromptVersion)
        .where(
            SystemPromptVersion.agent_id == agent_id,
            SystemPromptVersion.tenant_id == tenant_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one()
