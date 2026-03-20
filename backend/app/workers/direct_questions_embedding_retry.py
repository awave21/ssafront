from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import async_session_factory
from app.services.direct_questions.retry import retry_pending_direct_question_embeddings

logger = structlog.get_logger(__name__)


async def run_retry_loop() -> None:
    settings = get_settings()
    logger.info(
        "direct_question_embedding_retry_worker_started",
        interval_seconds=settings.direct_questions_retry_interval_seconds,
        batch_size=settings.direct_questions_retry_batch_size,
    )
    while True:
        try:
            async with async_session_factory() as db:
                await retry_pending_direct_question_embeddings(
                    db,
                    limit=settings.direct_questions_retry_batch_size,
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("direct_question_embedding_retry_worker_failed", error=str(exc))
        await asyncio.sleep(settings.direct_questions_retry_interval_seconds)


async def main() -> None:
    configure_logging()
    await run_retry_loop()


if __name__ == "__main__":
    asyncio.run(main())
