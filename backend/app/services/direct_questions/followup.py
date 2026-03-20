from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.channel import AgentChannel, Channel
from app.db.models.direct_question import DirectQuestion
from app.db.models.direct_question_followup_job import DirectQuestionFollowupJob
from app.services.agent_user_state import is_agent_user_disabled_by_session
from app.services.telegram import TelegramWebhookError, send_telegram_message

logger = structlog.get_logger(__name__)


def _parse_telegram_session(session_id: str) -> str | None:
    if not session_id or ":" not in session_id:
        return None
    platform, platform_user_id = session_id.split(":", 1)
    if platform.strip().lower() != "telegram":
        return None
    target = platform_user_id.strip()
    if not target:
        return None
    return target


def _extract_followup_payload(raw_followup: Any) -> tuple[bool, str, int]:
    if not isinstance(raw_followup, dict):
        return False, "", 0

    enabled = bool(raw_followup.get("enabled"))
    content = str(raw_followup.get("content") or "").strip()
    delay_minutes = raw_followup.get("delay_minutes", 0)
    try:
        delay = int(delay_minutes)
    except (TypeError, ValueError):
        delay = 0
    if not enabled or not content or not (1 <= delay <= 10080):
        return False, "", 0
    return True, content, delay


async def schedule_direct_question_followup(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    direct_question_id: UUID,
    run_id: UUID,
    session_id: str,
    followup: dict[str, Any] | None,
    max_attempts: int = 5,
) -> bool:
    enabled, content, delay_minutes = _extract_followup_payload(followup)
    if not enabled:
        return False

    telegram_target = _parse_telegram_session(session_id)
    if telegram_target is None:
        return False

    scheduled_at = datetime.utcnow() + timedelta(minutes=delay_minutes)
    stmt = (
        insert(DirectQuestionFollowupJob)
        .values(
            tenant_id=tenant_id,
            agent_id=agent_id,
            direct_question_id=direct_question_id,
            run_id=run_id,
            session_id=session_id,
            channel_type="telegram",
            channel_target=telegram_target,
            message_text=content,
            scheduled_at=scheduled_at,
            max_attempts=max(1, int(max_attempts)),
            status="pending",
        )
        .on_conflict_do_nothing(
            constraint="uq_dq_followup_job_run_question_session",
        )
    )
    result = await db.execute(stmt)
    return bool(result.rowcount)


async def _load_telegram_bot_token(db: AsyncSession, *, agent_id: UUID) -> str | None:
    stmt = (
        select(Channel.telegram_bot_token)
        .join(AgentChannel, AgentChannel.channel_id == Channel.id)
        .where(
            AgentChannel.agent_id == agent_id,
            Channel.is_deleted.is_(False),
            Channel.type == "telegram",
            Channel.telegram_webhook_enabled.is_(True),
            Channel.telegram_bot_token.is_not(None),
        )
        .order_by(AgentChannel.created_at.asc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def dispatch_due_followup_jobs(
    db: AsyncSession,
    *,
    limit: int,
) -> int:
    now = datetime.utcnow()
    stmt = (
        select(DirectQuestionFollowupJob)
        .where(
            DirectQuestionFollowupJob.status == "pending",
            DirectQuestionFollowupJob.scheduled_at <= now,
            or_(
                DirectQuestionFollowupJob.next_retry_at.is_(None),
                DirectQuestionFollowupJob.next_retry_at <= now,
            ),
        )
        .order_by(DirectQuestionFollowupJob.scheduled_at.asc())
        .with_for_update(skip_locked=True)
        .limit(limit)
    )
    jobs = (await db.execute(stmt)).scalars().all()
    if not jobs:
        return 0

    sent_count = 0
    for job in jobs:
        job.attempts += 1
        question = await db.get(DirectQuestion, job.direct_question_id)
        if question is None or not question.is_enabled:
            job.status = "cancelled"
            job.last_error = "direct_question_unavailable_or_disabled"
            continue

        if await is_agent_user_disabled_by_session(
            db,
            tenant_id=job.tenant_id,
            agent_id=job.agent_id,
            session_id=job.session_id,
        ):
            job.status = "cancelled"
            job.last_error = "agent_user_disabled"
            continue

        if job.channel_type != "telegram":
            job.status = "failed"
            job.last_error = "unsupported_channel_type"
            continue

        bot_token = await _load_telegram_bot_token(db, agent_id=job.agent_id)
        if not bot_token:
            if job.attempts >= job.max_attempts:
                job.status = "failed"
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=60)
            job.last_error = "telegram_bot_token_not_configured"
            continue

        try:
            await send_telegram_message(
                bot_token=bot_token,
                chat_id=job.channel_target,
                text=job.message_text,
            )
        except TelegramWebhookError as exc:
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.last_error = str(exc)
                continue

            retry_after = exc.retry_after_seconds or min(3600, 30 * (2 ** max(job.attempts - 1, 0)))
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=retry_after)
            job.last_error = str(exc)
            continue

        job.status = "sent"
        job.sent_at = datetime.utcnow()
        job.next_retry_at = None
        job.last_error = None
        sent_count += 1

    await db.commit()
    logger.info(
        "direct_question_followup_dispatch_completed",
        attempted=len(jobs),
        sent=sent_count,
    )
    return sent_count
