from __future__ import annotations

import hashlib
from dataclasses import dataclass

import redis.asyncio as aioredis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger()


@dataclass(slots=True)
class LoginBlockState:
    is_blocked: bool
    retry_after_seconds: int = 0
    reason: str | None = None


@dataclass(slots=True)
class _DimensionSpec:
    reason: str
    counter_key: str
    lock_key: str
    limit: int
    clear_on_success: bool


class LoginBruteforceGuard:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: aioredis.Redis | None = None

    def _is_enabled(self) -> bool:
        return bool(self._settings.auth_login_bruteforce_enabled and self._settings.redis_url)

    async def _get_redis(self) -> aioredis.Redis | None:
        if not self._is_enabled():
            return None

        if self._redis is None:
            self._redis = aioredis.from_url(
                self._settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    @staticmethod
    def _normalize_ip(ip_address: str | None) -> str:
        normalized = (ip_address or "unknown").strip()
        return normalized or "unknown"

    @staticmethod
    def _hash_value(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _extract_ipv4_subnet24(ip_address: str) -> str | None:
        parts = ip_address.split(".")
        if len(parts) != 4:
            return None

        try:
            octets = [int(part) for part in parts]
        except ValueError:
            return None

        if any(octet < 0 or octet > 255 for octet in octets):
            return None
        return f"{octets[0]}.{octets[1]}.{octets[2]}.0/24"

    def _build_dimension_specs(self, ip_address: str | None, normalized_email: str) -> list[_DimensionSpec]:
        safe_ip = self._normalize_ip(ip_address)
        ip_hash = self._hash_value(f"ip:{safe_ip}")
        email_hash = self._hash_value(f"email:{normalized_email}")
        pair_hash = self._hash_value(f"pair:{safe_ip}|{normalized_email}")

        specs: list[_DimensionSpec] = [
            _DimensionSpec(
                reason="ip_limit",
                counter_key=f"auth:login:failed:ip:{ip_hash}",
                lock_key=f"auth:login:lock:ip:{ip_hash}",
                limit=self._settings.auth_login_bruteforce_max_attempts_per_ip,
                clear_on_success=False,
            ),
            _DimensionSpec(
                reason="email_limit",
                counter_key=f"auth:login:failed:email:{email_hash}",
                lock_key=f"auth:login:lock:email:{email_hash}",
                limit=self._settings.auth_login_bruteforce_max_attempts_per_email,
                clear_on_success=True,
            ),
            _DimensionSpec(
                reason="pair_limit",
                counter_key=f"auth:login:failed:pair:{pair_hash}",
                lock_key=f"auth:login:lock:pair:{pair_hash}",
                limit=self._settings.auth_login_bruteforce_max_attempts_per_ip_email,
                clear_on_success=True,
            ),
        ]

        if self._settings.auth_login_bruteforce_subnet_enabled:
            subnet = self._extract_ipv4_subnet24(safe_ip)
            if subnet:
                subnet_hash = self._hash_value(f"subnet:{subnet}")
                specs.append(
                    _DimensionSpec(
                        reason="subnet_limit",
                        counter_key=f"auth:login:failed:subnet:{subnet_hash}",
                        lock_key=f"auth:login:lock:subnet:{subnet_hash}",
                        limit=self._settings.auth_login_bruteforce_max_attempts_per_subnet,
                        clear_on_success=False,
                    )
                )

        return specs

    def _calculate_lock_seconds(self, failed_count: int, limit: int) -> int:
        if not self._settings.auth_login_bruteforce_progressive_enabled:
            return max(self._settings.auth_login_bruteforce_window_seconds, 1)

        base_block = max(self._settings.auth_login_bruteforce_base_block_seconds, 1)
        extra_attempts = max(failed_count - limit, 0)
        multiplier = 2 ** min(extra_attempts, 10)
        progressive_block = base_block * multiplier

        # Не ослабляем старую защиту: базовый lock не меньше окна счётчиков.
        min_block = max(self._settings.auth_login_bruteforce_window_seconds, 1)
        max_block = max(
            self._settings.auth_login_bruteforce_max_block_seconds,
            base_block,
            min_block,
        )
        return min(max(progressive_block, min_block), max_block)

    @staticmethod
    async def _resolve_retry_after_by_ttls(
        redis_client: aioredis.Redis,
        keys: list[str],
        fallback_seconds: int,
    ) -> int:
        if not keys:
            return max(fallback_seconds, 1)

        pipeline = redis_client.pipeline(transaction=False)
        for key in keys:
            pipeline.ttl(key)
        ttl_values = await pipeline.execute()
        positive_ttls = [int(ttl) for ttl in ttl_values if isinstance(ttl, int) and ttl > 0]
        if positive_ttls:
            return max(positive_ttls)
        return max(fallback_seconds, 1)

    async def _upsert_lock_keys(
        self,
        redis_client: aioredis.Redis,
        lock_updates: list[tuple[str, int]],
    ) -> None:
        if not lock_updates:
            return

        ttl_pipeline = redis_client.pipeline(transaction=False)
        for lock_key, _ in lock_updates:
            ttl_pipeline.ttl(lock_key)
        existing_ttls = await ttl_pipeline.execute()

        set_pipeline = redis_client.pipeline(transaction=False)
        should_write = False
        for (lock_key, lock_seconds), existing_ttl in zip(lock_updates, existing_ttls):
            existing_ttl_int = int(existing_ttl) if isinstance(existing_ttl, int) else -1
            if existing_ttl_int >= lock_seconds:
                continue
            set_pipeline.set(lock_key, "1", ex=lock_seconds)
            should_write = True

        if should_write:
            await set_pipeline.execute()

    async def get_block_state(self, ip_address: str | None, normalized_email: str) -> LoginBlockState:
        redis_client = await self._get_redis()
        if redis_client is None:
            return LoginBlockState(is_blocked=False)

        specs = self._build_dimension_specs(ip_address, normalized_email)

        try:
            lock_pipeline = redis_client.pipeline(transaction=False)
            for spec in specs:
                lock_pipeline.ttl(spec.lock_key)
            lock_ttls = await lock_pipeline.execute()

            active_locks = [
                (spec.reason, int(ttl))
                for spec, ttl in zip(specs, lock_ttls)
                if isinstance(ttl, int) and ttl > 0
            ]
            if active_locks:
                reason, retry_after = max(active_locks, key=lambda item: item[1])
                return LoginBlockState(
                    is_blocked=True,
                    retry_after_seconds=retry_after,
                    reason=reason,
                )

            raw_counts = await redis_client.mget(*[spec.counter_key for spec in specs])
        except Exception as exc:
            logger.warning("auth_bruteforce_read_failed", error=str(exc))
            return LoginBlockState(is_blocked=False)

        exceeded: list[_DimensionSpec] = []
        for spec, raw_count in zip(specs, raw_counts):
            count = int(raw_count or 0)
            if spec.limit > 0 and count >= spec.limit:
                exceeded.append(spec)
        if not exceeded:
            return LoginBlockState(is_blocked=False)

        try:
            retry_after = await self._resolve_retry_after_by_ttls(
                redis_client=redis_client,
                keys=[spec.counter_key for spec in exceeded],
                fallback_seconds=self._settings.auth_login_bruteforce_window_seconds,
            )
        except Exception:
            # Если Redis недоступен для TTL, используем дефолт окна блокировки.
            retry_after = max(self._settings.auth_login_bruteforce_window_seconds, 1)

        return LoginBlockState(
            is_blocked=True,
            retry_after_seconds=retry_after,
            reason=exceeded[0].reason,
        )

    async def register_failed_attempt(self, ip_address: str | None, normalized_email: str) -> None:
        redis_client = await self._get_redis()
        if redis_client is None:
            return

        ttl = max(self._settings.auth_login_bruteforce_window_seconds, 1)
        specs = self._build_dimension_specs(ip_address, normalized_email)

        try:
            pipeline = redis_client.pipeline(transaction=False)
            for spec in specs:
                pipeline.incr(spec.counter_key)
                pipeline.expire(spec.counter_key, ttl)
            results = await pipeline.execute()

            lock_updates: list[tuple[str, int]] = []
            for index, spec in enumerate(specs):
                raw_count = results[index * 2]
                count = int(raw_count) if isinstance(raw_count, int) else int(raw_count or 0)
                if count < spec.limit:
                    continue
                lock_seconds = self._calculate_lock_seconds(count, spec.limit)
                lock_updates.append((spec.lock_key, lock_seconds))

            await self._upsert_lock_keys(redis_client, lock_updates)
        except Exception as exc:
            logger.warning("auth_bruteforce_write_failed", error=str(exc))

    async def clear_failed_attempts(self, ip_address: str | None, normalized_email: str) -> None:
        redis_client = await self._get_redis()
        if redis_client is None:
            return

        specs = [spec for spec in self._build_dimension_specs(ip_address, normalized_email) if spec.clear_on_success]
        keys_to_delete: list[str] = []
        for spec in specs:
            keys_to_delete.append(spec.counter_key)
            keys_to_delete.append(spec.lock_key)

        try:
            if keys_to_delete:
                await redis_client.delete(*keys_to_delete)
        except Exception as exc:
            logger.warning("auth_bruteforce_clear_failed", error=str(exc))


login_bruteforce_guard = LoginBruteforceGuard()
