#!/usr/bin/env python3
"""Проверка, подключён ли SQNS к агенту. Запуск из корня:
  PYTHONPATH=./backend DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agents \\
  python scripts/check_agent_sqns.py de1fc6a9-231b-4622-90a1-404bd7c778ca
"""
from __future__ import annotations

import os
import sys
from uuid import UUID

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db.models.agent import Agent


async def main(agent_id: str) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=1, max_overflow=0)
    async with engine.connect() as conn:
        r = await conn.execute(
            select(Agent).where(Agent.id == UUID(agent_id), Agent.is_deleted.is_(False))
        )
        a = r.fetchone()
        if not a:
            print(f"Агент {agent_id} не найден или удалён.")
            return

        print(f"Агент: {a.id}")
        print(f"  sqns_enabled:      {a.sqns_enabled}")
        print(f"  sqns_configured:   {a.sqns_configured}")
        print(f"  sqns_host:         {a.sqns_host}")
        print(f"  sqns_credential_id: {a.sqns_credential_id}")
        print(f"  sqns_status:       {a.sqns_status}")
        print(f"  sqns_error:        {a.sqns_error}")
        print(f"  sqns_last_sync_at: {a.sqns_last_sync_at}")
        print(f"  sqns_last_activity_at: {a.sqns_last_activity_at}")

        if a.sqns_enabled and a.sqns_configured and a.sqns_host and a.sqns_credential_id:
            print("\nSQNS подключён к агенту.")
        else:
            print("\nSQNS не подключён (нужны sqns_enabled, sqns_configured, sqns_host, sqns_credential_id).")


if __name__ == "__main__":
    import asyncio
    aid = sys.argv[1] if len(sys.argv) > 1 else "de1fc6a9-231b-4622-90a1-404bd7c778ca"
    asyncio.run(main(aid))
