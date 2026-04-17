"""Фоновый воркер: отправка отложенных сообщений сценариев."""

from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import async_session_factory
from app.services.scenario_delayed_messages import dispatch_due_scenario_messages

logger = structlog.get_logger(__name__)


async def run_dispatch_loop() -> None:
    settings = get_settings()
    interval_seconds = settings.scenario_delayed_dispatch_interval_seconds
    batch_size = settings.scenario_delayed_dispatch_batch_size
    logger.info(
        "scenario_delayed_dispatch_worker_started",
        interval_seconds=interval_seconds,
        batch_size=batch_size,
    )

    while True:
        try:
            async with async_session_factory() as db:
                await dispatch_due_scenario_messages(db, limit=batch_size)
        except Exception as exc:  # noqa: BLE001
            logger.exception("scenario_delayed_dispatch_worker_failed", error=str(exc))
        await asyncio.sleep(interval_seconds)


async def main() -> None:
    configure_logging()
    await run_dispatch_loop()


if __name__ == "__main__":
    asyncio.run(main())
