#!/usr/bin/env python3
"""
Скрипт привязки JWT/Bearer SQNS к агенту. В контейнере API (PYTHONPATH=/app, DATABASE_URL@db):
  python /app/scripts/link_sqns_to_agent.py --agent-id <UUID> --token "<JWT>" --host "https://..."
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import get_settings
from app.db.models.agent import Agent
from app.db.models.credential import Credential
from app.services.credentials import encrypt_config


async def main(agent_id: str, token: str, host: str) -> None:
    settings = get_settings()
    if not settings.credentials_encryption_key:
        print("Внимание: CREDENTIALS_ENCRYPTION_KEY не задан, config сохранится без шифрования.")

    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        uid = UUID(agent_id)
        r = await db.execute(select(Agent).where(Agent.id == uid, Agent.is_deleted.is_(False)))
        agent = r.scalar_one_or_none()
        if not agent:
            print(f"Агент {agent_id} не найден или удалён.")
            return

        tenant_id = agent.tenant_id
        name = f"sqns-{agent.id}"
        config = {"value": token, "direct_bearer": True}
        encrypted = encrypt_config(config)

        r = await db.execute(
            select(Credential).where(
                Credential.tenant_id == tenant_id,
                Credential.name == name,
            )
        )
        cred = r.scalar_one_or_none()
        if cred:
            cred.config = encrypted
            cred.auth_type = "api_key"
            cred.is_active = True
        else:
            cred = Credential(
                tenant_id=tenant_id,
                name=name,
                auth_type="api_key",
                config=encrypted,
                is_active=True,
            )
            db.add(cred)
            await db.flush()

        agent.sqns_enabled = True
        agent.sqns_configured = True
        agent.sqns_host = host.rstrip("/")
        agent.sqns_credential_id = cred.id
        agent.sqns_status = "ok"
        agent.sqns_error = None
        agent.sqns_last_sync_at = datetime.utcnow()
        agent.sqns_last_activity_at = agent.sqns_last_sync_at

        await db.commit()
        print(f"Готово: агент {agent_id} связан с SQNS host={host}, credential_id={cred.id}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--host", required=True)
    args = ap.parse_args()
    asyncio.run(main(args.agent_id, args.token, args.host))
