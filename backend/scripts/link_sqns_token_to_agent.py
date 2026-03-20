#!/usr/bin/env python3
"""
Скрипт привязки готового JWT/Bearer-токена SQNS к агенту без перевыпуска.
Пишет в БД: credential (encrypted) + обновляет agent (sqns_*).

Запуск (из корня проекта):
  PYTHONPATH=./backend DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agents \\
  python scripts/link_sqns_token_to_agent.py \\
    --agent-id de1fc6a9-231b-4622-90a1-404bd7c778ca \\
    --token "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \\
    --host "https://crmexchange.1denta.ru"

Если API и БД в Docker: либо DATABASE_URL=...@localhost:5432 (порт проброшен),
либо запустить внутри контейнера API:
  docker exec -i agentsapp-api-1 python -c "
import asyncio, os, sys
sys.path.insert(0, '/app')
os.chdir('/app')
from app.db.session import async_session_factory
from app.db.models.agent import Agent
from app.db.models.credential import Credential
from app.services.credentials import encrypt_config
from sqlalchemy import select

async def run():
    agent_id = 'de1fc6a9-231b-4622-90a1-404bd7c778ca'
    token = 'eyJ...'
    host = 'https://crmexchange.1denta.ru'
    ...
  "
Проще использовать этот скрипт с хоста и DATABASE_URL=...@localhost:5432.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from uuid import UUID

# чтобы импортировать app
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

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
    ap = argparse.ArgumentParser(description="Привязать SQNS JWT/Bearer к агенту")
    ap.add_argument("--agent-id", required=True, help="UUID агента")
    ap.add_argument("--token", required=True, help="JWT или Bearer-токен SQNS")
    ap.add_argument("--host", required=True, help="Базовый URL SQNS, например https://crmexchange.1denta.ru")
    args = ap.parse_args()
    asyncio.run(main(args.agent_id, args.token, args.host))
