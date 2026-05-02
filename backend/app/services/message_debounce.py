"""Debounce входящих сообщений: короткие ждут дольше, длинные — быстрее."""

from __future__ import annotations

import asyncio
import json
import structlog

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_BUFFER_TTL_SECONDS = 120  # TTL ключей в Redis (страховка от утечек)


def _debounce_delay(text: str) -> float:
    """Задержка перед запуском агента в зависимости от длины сообщения."""
    length = len(text)
    if length < 20:
        return 10.0
    if length < 80:
        return 6.0
    return 3.0


def _redis_keys(session_key: str) -> tuple[str, str, str]:
    """Ключи Redis: буфер текста, список message_id, версия."""
    return (
        f"debounce:buf:{session_key}",
        f"debounce:ids:{session_key}",
        f"debounce:ver:{session_key}",
    )


async def _get_redis() -> aioredis.Redis:
    settings = get_settings()
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def append_message(session_key: str, text: str, message_id: str | None = None) -> None:
    """Дописать текст и message_id в буфер."""
    buf_key, ids_key, _ = _redis_keys(session_key)
    redis = await _get_redis()
    try:
        async with redis.pipeline() as pipe:
            exists = await redis.exists(buf_key)
            pipe.append(buf_key, ("\n" + text) if exists else text)
            pipe.expire(buf_key, _BUFFER_TTL_SECONDS)
            if message_id:
                pipe.rpush(ids_key, message_id)
                pipe.expire(ids_key, _BUFFER_TTL_SECONDS)
            await pipe.execute()
    finally:
        await redis.aclose()


async def flush_buffer(session_key: str) -> tuple[str | None, list[str]]:
    """Забрать и очистить буфер. Возвращает (text, [message_ids])."""
    buf_key, ids_key, _ = _redis_keys(session_key)
    redis = await _get_redis()
    try:
        async with redis.pipeline() as pipe:
            pipe.getdel(buf_key)
            pipe.lrange(ids_key, 0, -1)
            pipe.delete(ids_key)
            results = await pipe.execute()
        text = results[0]
        ids = results[1] or []
        return (text.strip() if text else None), ids
    finally:
        await redis.aclose()


async def bump_version(session_key: str) -> int:
    """Инкрементировать версию — сигнал, что пришло новое сообщение."""
    _, _, ver_key = _redis_keys(session_key)
    redis = await _get_redis()
    try:
        ver = await redis.incr(ver_key)
        await redis.expire(ver_key, _BUFFER_TTL_SECONDS)
        return ver
    finally:
        await redis.aclose()


async def get_version(session_key: str) -> int:
    """Прочитать текущую версию."""
    _, _, ver_key = _redis_keys(session_key)
    redis = await _get_redis()
    try:
        val = await redis.get(ver_key)
        return int(val) if val else 0
    finally:
        await redis.aclose()


async def debounce_and_run(
    session_key: str,
    text: str,
    callback,  # async callable(aggregated_text: str, message_ids: list[str]) -> None
    message_id: str | None = None,
) -> None:
    """
    Добавить текст в буфер и запустить задачу с задержкой.

    Если за время задержки придёт новое сообщение — версия изменится
    и эта задача тихо завершится без вызова callback.

    callback получает агрегированный текст и список всех provider_message_id
    из сообщений которые попали в этот debounce-батч.
    """
    await append_message(session_key, text, message_id)
    version = await bump_version(session_key)
    delay = _debounce_delay(text)

    logger.info(
        "debounce_scheduled",
        session_key=session_key,
        text_len=len(text),
        delay=delay,
        version=version,
    )

    async def _run() -> None:
        await asyncio.sleep(delay)

        current_version = await get_version(session_key)
        if current_version != version:
            logger.info(
                "debounce_cancelled",
                session_key=session_key,
                scheduled_version=version,
                current_version=current_version,
            )
            return

        aggregated, message_ids = await flush_buffer(session_key)
        if not aggregated:
            return

        logger.info(
            "debounce_fired",
            session_key=session_key,
            aggregated_len=len(aggregated),
            message_ids_count=len(message_ids),
            version=version,
        )
        await callback(aggregated, message_ids)

    asyncio.create_task(_run())
