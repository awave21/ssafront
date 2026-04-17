"""Сервис для управления статусом диалогов (per-chat pause/disable)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.dialog_state import DialogState

logger = structlog.get_logger(__name__)


async def is_dialog_active(
    db: AsyncSession,
    agent_id: UUID | Any,
    session_id: str,
) -> bool:
    """Проверить, что диалог активен. Если записи нет — считаем active.

    Legacy-статус `paused` не должен блокировать ответы сам по себе:
    фактическая автопауза менеджера определяется отдельно через
    `is_manager_paused` и `last_manager_message_at`.
    """
    stmt = select(DialogState.status).where(
        DialogState.session_id == session_id,
        DialogState.agent_id == agent_id,
    )
    result = await db.execute(stmt)
    status_value = result.scalar_one_or_none()
    return status_value is None or status_value != "disabled"


async def _get_or_create_state(
    db: AsyncSession,
    agent_id: UUID | Any,
    tenant_id: UUID | Any,
    session_id: str,
) -> tuple[DialogState, bool]:
    """Получить или создать DialogState. Возвращает (state, is_new)."""
    stmt = select(DialogState).where(
        DialogState.session_id == session_id,
        DialogState.agent_id == agent_id,
    )
    state = (await db.execute(stmt)).scalar_one_or_none()
    if state is not None:
        return state, False
    state = DialogState(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
    )
    db.add(state)
    return state, True


async def set_dialog_status(
    db: AsyncSession,
    *,
    agent_id: UUID | Any,
    tenant_id: UUID | Any,
    session_id: str,
    new_status: str,
) -> DialogState:
    """Создать или обновить статус диалога (upsert)."""
    state, _ = await _get_or_create_state(db, agent_id, tenant_id, session_id)
    state.status = new_status
    await db.commit()
    logger.info("dialog_status_changed", agent_id=str(agent_id), session_id=session_id, new_status=new_status)
    return state


async def upsert_dialog_status_flush_only(
    db: AsyncSession,
    *,
    agent_id: UUID | Any,
    tenant_id: UUID | Any,
    session_id: str,
    new_status: str,
) -> DialogState:
    """Обновить статус диалога без commit (для function-rules внутри транзакции)."""
    state, _ = await _get_or_create_state(db, agent_id, tenant_id, session_id)
    state.status = new_status
    await db.flush()
    logger.info("dialog_status_flush", agent_id=str(agent_id), session_id=session_id, new_status=new_status)
    return state


async def is_manager_paused(
    db: AsyncSession,
    agent_id: UUID | Any,
    session_id: str,
) -> bool:
    """
    Проверить, стоит ли агент на автопаузе из-за активности менеджера.

    Настройка manager_pause_minutes — глобальная для агента (из таблицы agents).
    Время последнего сообщения менеджера — per-dialog (из таблицы dialog_states).

    Возвращает True, если менеджер отправлял сообщение в этот диалог
    и прошло меньше manager_pause_minutes минут.
    """
    # Получаем last_manager_message_at из dialog_states
    ds_stmt = select(DialogState.last_manager_message_at).where(
        DialogState.session_id == session_id,
        DialogState.agent_id == agent_id,
    )
    last_msg_at = (await db.execute(ds_stmt)).scalar_one_or_none()
    if not last_msg_at:
        return False

    # Получаем manager_pause_minutes из agents (глобальная настройка)
    agent_stmt = select(Agent.manager_pause_minutes).where(Agent.id == agent_id)
    pause_minutes = (await db.execute(agent_stmt)).scalar_one_or_none()
    if not pause_minutes:
        pause_minutes = 10  # default

    pause_until = last_msg_at + timedelta(minutes=pause_minutes)
    now = datetime.now(timezone.utc)
    is_paused = now < pause_until
    if is_paused:
        logger.info(
            "manager_pause_active",
            agent_id=str(agent_id),
            session_id=session_id,
            pause_minutes=pause_minutes,
            pause_until=pause_until.isoformat(),
            remaining_seconds=int((pause_until - now).total_seconds()),
        )
    return is_paused


async def update_last_manager_message(
    db: AsyncSession,
    *,
    agent_id: UUID | Any,
    tenant_id: UUID | Any,
    session_id: str,
) -> DialogState:
    """Обновить время последнего сообщения менеджера (upsert)."""
    state, _ = await _get_or_create_state(db, agent_id, tenant_id, session_id)
    state.last_manager_message_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("last_manager_message_updated", agent_id=str(agent_id), session_id=session_id)
    return state


async def get_last_user_message_at(
    db: AsyncSession,
    *,
    agent_id: UUID | Any,
    session_id: str,
) -> datetime | None:
    """Время последнего входящего сообщения клиента (если запись dialog_states есть)."""
    stmt = select(DialogState.last_user_message_at).where(
        DialogState.session_id == session_id,
        DialogState.agent_id == agent_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def update_last_user_message_at(
    db: AsyncSession,
    *,
    agent_id: UUID | Any,
    tenant_id: UUID | Any,
    session_id: str,
    commit: bool = True,
) -> DialogState:
    """Обновить время последнего сообщения клиента (upsert)."""
    state, _ = await _get_or_create_state(db, agent_id, tenant_id, session_id)
    state.last_user_message_at = datetime.now(timezone.utc)
    if commit:
        await db.commit()
    else:
        await db.flush()
    logger.info("last_user_message_at_updated", agent_id=str(agent_id), session_id=session_id)
    return state
