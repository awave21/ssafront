from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.models.agent import Agent
from app.db.session import async_session_factory
from app.services.sqns.client_factory import SqnsClientConfigurationError, build_sqns_client_for_agent
from app.services.sqns.sync import sync_sqns_entities
from app.services.sqns.sync_locks import sqns_agent_lock
from app.services.graphrag_export.corpus_dispatch import maybe_auto_dispatch_graphrag_corpus

logger = structlog.get_logger(__name__)


async def _load_enabled_agent_ids(offset: int, limit: int) -> list[UUID]:
    async with async_session_factory() as db:
        stmt = (
            select(Agent.id)
            .where(
                Agent.sqns_enabled == True,
                Agent.sqns_host.is_not(None),
                Agent.sqns_credential_id.is_not(None),
                Agent.is_deleted == False,
            )
            .order_by(Agent.created_at)
            .offset(offset)
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        return [agent_id for (agent_id,) in rows]


async def _sync_agent(agent_id: UUID) -> None:
    async with async_session_factory() as db:
        agent = await db.get(Agent, agent_id)
        if agent is None or not agent.sqns_enabled:
            return

        try:
            sqns_client = await build_sqns_client_for_agent(db, agent)
        except SqnsClientConfigurationError as exc:
            agent.sqns_status = "error"
            agent.sqns_error = str(exc)
            agent.sqns_last_activity_at = datetime.utcnow()
            await db.commit()
            logger.warning(
                "sqns_worker_agent_skipped_configuration_error",
                agent_id=str(agent_id),
                error=str(exc),
            )
            return

        async with sqns_agent_lock(agent_id) as acquired:
            if not acquired:
                logger.info("sqns_worker_agent_skipped_lock", agent_id=str(agent_id))
                return

            result = await sync_sqns_entities(
                db=db,
                sqns_client=sqns_client,
                agent_id=agent_id,
                trigger="hourly_worker",
            )
            if result.success:
                agent.sqns_status = "ok"
                agent.sqns_error = None
                agent.sqns_last_sync_at = result.synced_at
                agent.sqns_last_activity_at = result.synced_at
            else:
                agent.sqns_status = "error"
                agent.sqns_error = result.message[:2000]
                agent.sqns_last_activity_at = datetime.utcnow()
            await db.commit()
            if result.success:
                await maybe_auto_dispatch_graphrag_corpus(agent.id, agent.tenant_id)


async def run_hourly_sync_loop() -> None:
    settings = get_settings()
    interval_seconds = settings.sqns_sync_interval_seconds
    batch_size = settings.sqns_sync_batch_size

    logger.info(
        "sqns_worker_started",
        interval_seconds=interval_seconds,
        batch_size=batch_size,
    )

    while True:
        cycle_started = datetime.now(timezone.utc)
        processed = 0
        failed = 0
        offset = 0

        try:
            while True:
                agent_ids = await _load_enabled_agent_ids(offset=offset, limit=batch_size)
                if not agent_ids:
                    break

                for agent_id in agent_ids:
                    try:
                        await _sync_agent(agent_id)
                        processed += 1
                    except Exception as exc:
                        failed += 1
                        logger.exception(
                            "sqns_worker_agent_sync_failed",
                            agent_id=str(agent_id),
                            error=str(exc),
                        )
                offset += len(agent_ids)
        except Exception as exc:
            logger.exception("sqns_worker_cycle_failed", error=str(exc))

        elapsed_seconds = (datetime.now(timezone.utc) - cycle_started).total_seconds()
        sleep_seconds = max(int(interval_seconds - elapsed_seconds), 5)
        logger.info(
            "sqns_worker_cycle_completed",
            processed=processed,
            failed=failed,
            elapsed_seconds=elapsed_seconds,
            sleep_seconds=sleep_seconds,
        )
        await asyncio.sleep(sleep_seconds)


async def main() -> None:
    configure_logging()
    await run_hourly_sync_loop()


if __name__ == "__main__":
    asyncio.run(main())
