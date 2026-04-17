"""Диспетчер отложенных сообщений сценариев (таблица scenario_delayed_messages)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario_delayed_message import ScenarioDelayedMessage
from app.services.agent_user_state import is_agent_user_disabled_by_session
from app.services.outbound.manager_dispatcher import ManagerDispatchError, dispatch_manager_message

logger = structlog.get_logger(__name__)


async def dispatch_due_scenario_messages(
    db: AsyncSession,
    *,
    limit: int,
) -> int:
    """Отправить сообщения с scheduled_at <= now. Возвращает число успешно отправленных."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(ScenarioDelayedMessage)
        .where(
            ScenarioDelayedMessage.status == "pending",
            ScenarioDelayedMessage.scheduled_at <= now,
            or_(
                ScenarioDelayedMessage.next_retry_at.is_(None),
                ScenarioDelayedMessage.next_retry_at <= now,
            ),
        )
        .order_by(ScenarioDelayedMessage.scheduled_at.asc())
        .with_for_update(skip_locked=True)
        .limit(limit)
    )
    jobs = (await db.execute(stmt)).scalars().all()
    if not jobs:
        return 0

    sent_count = 0
    for job in jobs:
        job.attempts += 1

        if await is_agent_user_disabled_by_session(
            db,
            tenant_id=job.tenant_id,
            agent_id=job.agent_id,
            session_id=job.session_id,
        ):
            job.status = "cancelled"
            job.last_error = "agent_user_disabled"
            continue

        dialog_id = f"{job.channel_type}:{job.channel_target}"
        try:
            await dispatch_manager_message(
                db,
                agent_id=job.agent_id,
                dialog_id=dialog_id,
                content=job.message_text,
                manager_user_id=None,
            )
        except ManagerDispatchError as exc:
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.last_error = str(exc)
                continue
            retry_after = min(3600, 30 * (2 ** max(job.attempts - 1, 0)))
            job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_after)
            job.last_error = str(exc)
            continue
        except Exception as exc:  # noqa: BLE001
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.last_error = str(exc)
                continue
            job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=60)
            job.last_error = str(exc)
            continue

        job.status = "sent"
        job.sent_at = datetime.now(timezone.utc)
        job.next_retry_at = None
        job.last_error = None
        sent_count += 1

    await db.commit()
    logger.info(
        "scenario_delayed_dispatch_completed",
        attempted=len(jobs),
        sent=sent_count,
    )
    return sent_count
