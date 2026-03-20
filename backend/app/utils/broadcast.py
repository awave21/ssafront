"""
Redis-backed broadcaster для межпроцессной доставки событий.

Gunicorn запускает несколько воркеров (отдельные процессы).
WebSocket может быть на воркере A, а Telegram webhook обработан на воркере B.
In-memory asyncio.Queue не работает между процессами.
Redis pub/sub решает эту проблему.
"""
import asyncio
import json
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


class RedisBroadcaster:
    """
    Broadcaster на базе Redis pub/sub.
    
    publish() -> redis PUBLISH на канал agent:{agent_id}
    subscribe() -> возвращает asyncio.Queue, которая наполняется из redis SUBSCRIBE
    """

    def __init__(self) -> None:
        self._redis = None
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._listener_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def _get_channel(self, agent_id: str) -> str:
        return f"agent:{agent_id}:events"

    async def _get_redis(self):
        """Lazy-инициализация Redis соединения для публикации."""
        if self._redis is None:
            import redis.asyncio as aioredis
            from app.core.config import get_settings
            settings = get_settings()
            self._redis = aioredis.from_url(
                settings.redis_url or "redis://redis:6379/0",
                decode_responses=True,
            )
        return self._redis

    async def _listener(self, agent_id: str) -> None:
        """
        Фоновая задача: слушает Redis канал и раздаёт в локальные очереди.
        По одной задаче на каждый agent_id, к которому есть подписчики.
        """
        import redis.asyncio as aioredis
        from app.core.config import get_settings
        settings = get_settings()

        channel_name = self._get_channel(agent_id)
        
        # Создаём отдельное соединение для подписки (Redis требует dedicated connection для subscribe)
        sub_redis = aioredis.from_url(
            settings.redis_url or "redis://redis:6379/0",
            decode_responses=True,
        )
        pubsub = sub_redis.pubsub()
        
        try:
            await pubsub.subscribe(channel_name)
            logger.info("redis_subscribed", agent_id=agent_id, channel=channel_name)

            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if msg is None:
                    # Проверяем, есть ли ещё подписчики
                    async with self._lock:
                        if agent_id not in self._subscribers or not self._subscribers[agent_id]:
                            break
                    continue

                if msg["type"] != "message":
                    continue

                try:
                    data = json.loads(msg["data"])
                except (json.JSONDecodeError, TypeError):
                    logger.warning("redis_invalid_message", agent_id=agent_id, data=msg.get("data"))
                    continue

                # Раздаём всем локальным подписчикам (WebSocket'ам этого воркера)
                async with self._lock:
                    queues = list(self._subscribers.get(agent_id, set()))

                if queues:
                    logger.debug(
                        "redis_delivering",
                        agent_id=agent_id,
                        message_type=data.get("type") if isinstance(data, dict) else None,
                        local_subscribers=len(queues),
                    )

                for queue in queues:
                    try:
                        await queue.put(data)
                    except Exception as e:
                        logger.error("redis_deliver_error", agent_id=agent_id, error=str(e))

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("redis_listener_error", agent_id=agent_id, error=str(e))
        finally:
            try:
                await pubsub.unsubscribe(channel_name)
                await pubsub.close()
                await sub_redis.close()
            except Exception:
                pass
            logger.info("redis_unsubscribed", agent_id=agent_id, channel=channel_name)

    async def subscribe(self, agent_id: str | UUID) -> asyncio.Queue:
        agent_id = str(agent_id)
        queue: asyncio.Queue = asyncio.Queue()

        async with self._lock:
            if agent_id not in self._subscribers:
                self._subscribers[agent_id] = set()
            self._subscribers[agent_id].add(queue)

            # Если нет listener задачи для этого agent_id — запускаем
            if agent_id not in self._listener_tasks or self._listener_tasks[agent_id].done():
                self._listener_tasks[agent_id] = asyncio.create_task(
                    self._listener(agent_id)
                )

        logger.info(
            "broadcast_subscribe",
            agent_id=agent_id,
            local_subscribers=len(self._subscribers[agent_id]),
        )
        return queue

    async def unsubscribe(self, agent_id: str | UUID, queue: asyncio.Queue) -> None:
        agent_id = str(agent_id)

        async with self._lock:
            if agent_id in self._subscribers:
                self._subscribers[agent_id].discard(queue)
                if not self._subscribers[agent_id]:
                    del self._subscribers[agent_id]
                    # Отменяем listener если нет подписчиков
                    task = self._listener_tasks.pop(agent_id, None)
                    if task and not task.done():
                        task.cancel()

        logger.info("broadcast_unsubscribe", agent_id=agent_id)

    async def publish(self, agent_id: str | UUID, message: Any) -> None:
        """Публикует событие в Redis канал. Все воркеры получат его."""
        agent_id = str(agent_id)
        channel_name = self._get_channel(agent_id)

        try:
            r = await self._get_redis()
            payload = json.dumps(message, ensure_ascii=False, default=str)
            receivers = await r.publish(channel_name, payload)
            logger.info(
                "broadcast_published",
                agent_id=agent_id,
                channel=channel_name,
                message_type=message.get("type") if isinstance(message, dict) else None,
                redis_receivers=receivers,
            )
        except Exception as e:
            logger.error(
                "broadcast_publish_error",
                agent_id=agent_id,
                error=str(e),
            )


# Глобальный экземпляр брокера
broadcaster = RedisBroadcaster()
