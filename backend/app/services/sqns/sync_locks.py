from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory


class SqnsAgentAdvisoryLock:
    def __init__(self, agent_id: UUID):
        self.agent_id = agent_id
        self._lock_key = self._build_lock_key(agent_id)
        self._session_ctx = None
        self._session: AsyncSession | None = None
        self._acquired = False

    @staticmethod
    def _build_lock_key(agent_id: UUID) -> int:
        digest = hashlib.blake2b(str(agent_id).encode("utf-8"), digest_size=8).digest()
        unsigned_value = int.from_bytes(digest, byteorder="big", signed=False)
        if unsigned_value >= 2**63:
            return unsigned_value - 2**64
        return unsigned_value

    async def acquire(self) -> bool:
        self._session_ctx = async_session_factory()
        self._session = await self._session_ctx.__aenter__()
        result = await self._session.execute(
            text("SELECT pg_try_advisory_lock(:lock_key)"),
            {"lock_key": self._lock_key},
        )
        self._acquired = bool(result.scalar())
        if not self._acquired:
            await self.release()
        return self._acquired

    async def release(self) -> None:
        try:
            if self._session is not None and self._acquired:
                await self._session.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": self._lock_key},
                )
        finally:
            self._acquired = False
            if self._session_ctx is not None:
                await self._session_ctx.__aexit__(None, None, None)
            self._session = None
            self._session_ctx = None


@asynccontextmanager
async def sqns_agent_lock(agent_id: UUID):
    lock = SqnsAgentAdvisoryLock(agent_id)
    acquired = await lock.acquire()
    try:
        yield acquired
    finally:
        await lock.release()
