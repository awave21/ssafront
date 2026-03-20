from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsClientRecord
from app.services.sqns.client import SQNSClient
from app.services.sqns.client_pii import encrypt_client_pii, split_client_payload
from app.services.sqns.sync_handlers.common import parse_decimal, parse_int

logger = structlog.get_logger(__name__)


class SqnsClientsSyncHandler:
    def __init__(self, db: AsyncSession, client: SQNSClient, agent_id: UUID):
        self.db = db
        self.client = client
        self.agent_id = agent_id

    async def sync(self, *, modificate: int | None) -> dict[str, int]:
        synced_at = datetime.now(timezone.utc)
        clients = await self.client.list_all_clients(per_page=100, modificate=modificate)
        clients_synced = 0

        for client_payload in clients:
            if not isinstance(client_payload, dict):
                continue
            external_id = parse_int(client_payload.get("id"))
            if external_id is None:
                continue

            safe_payload, pii_payload = split_client_payload(client_payload)
            encrypted_pii = encrypt_client_pii(pii_payload)

            raw_tags = safe_payload.get("tags")
            tags = raw_tags if isinstance(raw_tags, list) else None

            stmt = insert(SqnsClientRecord).values(
                id=uuid4(),
                agent_id=self.agent_id,
                external_id=external_id,
                sex=parse_int(safe_payload.get("sex")),
                client_type=str(safe_payload.get("type")).strip() if safe_payload.get("type") is not None else None,
                visits_count=parse_int(safe_payload.get("visitsCount")),
                total_arrival=parse_decimal(safe_payload.get("totalArrival")),
                tags=tags,
                pii_data=encrypted_pii,
                raw_data=safe_payload,
                synced_at=synced_at,
                created_at=synced_at,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_sqns_clients_agent_external",
                set_={
                    "sex": stmt.excluded.sex,
                    "client_type": stmt.excluded.client_type,
                    "visits_count": stmt.excluded.visits_count,
                    "total_arrival": stmt.excluded.total_arrival,
                    "tags": stmt.excluded.tags,
                    "pii_data": stmt.excluded.pii_data,
                    "raw_data": stmt.excluded.raw_data,
                    "synced_at": stmt.excluded.synced_at,
                    "updated_at": synced_at,
                },
            )
            await self.db.execute(stmt)
            clients_synced += 1

        logger.info(
            "sqns_sync_clients_completed",
            agent_id=str(self.agent_id),
            clients_synced=clients_synced,
            modificate=modificate,
        )
        return {"clients_synced": clients_synced}
