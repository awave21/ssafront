from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsVisit
from app.services.sqns.client import SQNSClient
from app.services.sqns.sync_handlers.common import parse_bool, parse_datetime, parse_decimal, parse_int

logger = structlog.get_logger(__name__)


class SqnsVisitsSyncHandler:
    def __init__(self, db: AsyncSession, client: SQNSClient, agent_id: UUID):
        self.db = db
        self.client = client
        self.agent_id = agent_id

    async def sync(
        self,
        *,
        date_from: str,
        date_till: str,
        modificate: int | None,
    ) -> dict[str, int]:
        synced_at = datetime.now(timezone.utc)
        visits = await self.client.list_all_visits(
            date_from,
            date_till,
            per_page=100,
            modificate=modificate,
        )
        visits_synced = 0

        for visit in visits:
            if not isinstance(visit, dict):
                continue
            external_id = parse_int(visit.get("id"))
            if external_id is None:
                continue

            stmt = insert(SqnsVisit).values(
                id=uuid4(),
                agent_id=self.agent_id,
                external_id=external_id,
                resource_external_id=parse_int(visit.get("resourceId")),
                client_external_id=parse_int(visit.get("clientId")),
                visit_datetime=parse_datetime(visit.get("datetime")),
                attendance=parse_int(visit.get("attendance")),
                deleted=parse_bool(visit.get("deleted"), default=False),
                online=parse_bool(visit.get("online"), default=False),
                total_price=parse_decimal(visit.get("totalPrice")),
                total_cost=parse_decimal(visit.get("totalCost")),
                comment=str(visit.get("comment")).strip() if visit.get("comment") is not None else None,
                raw_data=visit,
                synced_at=synced_at,
                created_at=synced_at,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_sqns_visits_agent_external",
                set_={
                    "resource_external_id": stmt.excluded.resource_external_id,
                    "client_external_id": stmt.excluded.client_external_id,
                    "visit_datetime": stmt.excluded.visit_datetime,
                    "attendance": stmt.excluded.attendance,
                    "deleted": stmt.excluded.deleted,
                    "online": stmt.excluded.online,
                    "total_price": stmt.excluded.total_price,
                    "total_cost": stmt.excluded.total_cost,
                    "comment": stmt.excluded.comment,
                    "raw_data": stmt.excluded.raw_data,
                    "synced_at": stmt.excluded.synced_at,
                    "updated_at": synced_at,
                },
            )
            await self.db.execute(stmt)
            visits_synced += 1

        logger.info(
            "sqns_sync_visits_completed",
            agent_id=str(self.agent_id),
            visits_synced=visits_synced,
            modificate=modificate,
            date_from=date_from,
            date_till=date_till,
        )
        return {"visits_synced": visits_synced}
