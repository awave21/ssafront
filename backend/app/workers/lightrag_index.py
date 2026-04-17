"""Фоновый воркер: индексация опубликованных expert script flows в LightRAG."""

from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import async_session_factory
from app.services.script_flow_indexing import process_pending_script_flow_indexes

logger = structlog.get_logger(__name__)


async def run_loop() -> None:
    settings = get_settings()
    logger.info(
        "lightrag_index_worker_started",
        interval_seconds=settings.lightrag_index_poll_interval_seconds,
        batch_size=settings.lightrag_index_batch_size,
    )

    while True:
        settings = get_settings()
        interval = settings.lightrag_index_poll_interval_seconds
        batch = settings.lightrag_index_batch_size
        try:
            if not settings.lightrag_enabled:
                await asyncio.sleep(interval)
                continue
            async with async_session_factory() as db:
                n = await process_pending_script_flow_indexes(db, limit=batch)
                if n:
                    logger.info("lightrag_index_worker_batch", processed=n)
        except Exception as exc:  # noqa: BLE001
            logger.exception("lightrag_index_worker_failed", error=str(exc))
        await asyncio.sleep(interval)


async def main() -> None:
    configure_logging()
    await run_loop()


if __name__ == "__main__":
    asyncio.run(main())
