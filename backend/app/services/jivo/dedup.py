"""Дедупликация входящих событий Jivo.

Jivo при таймауте (3 сек) повторяет доставку до 2 раз — то же событие может прийти
2–3 раза. Чтобы не запускать агента повторно и не слать двойные ответы, помечаем
event.id в Redis (SET NX EX). Первый вызов возвращает True, повторные — False.
"""

from __future__ import annotations

import redis.asyncio as aioredis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_DEDUP_TTL_SECONDS = 3600


async def claim_event(event_id: str | None, ttl_seconds: int = _DEDUP_TTL_SECONDS) -> bool:
    """True — событие новое (можно обрабатывать); False — дубликат (уже видели).

    Если event_id пуст или Redis недоступен — возвращаем True (fail-open: лучше
    обработать, чем потерять сообщение).
    """
    if not event_id:
        return True
    settings = get_settings()
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        was_set = await redis.set(f"jivo:evt:{event_id}", "1", nx=True, ex=ttl_seconds)
        return bool(was_set)
    except Exception as exc:  # noqa: BLE001
        logger.warning("jivo_dedup_redis_error", event_id=event_id, error=str(exc))
        return True
    finally:
        await redis.aclose()
