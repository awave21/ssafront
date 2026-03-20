from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsCommodity
from app.services.sqns.client import SQNSClient
from app.services.sqns.sync_handlers.common import coerce_number

logger = structlog.get_logger(__name__)


class SqnsCommoditiesSyncHandler:
    def __init__(self, db: AsyncSession, client: SQNSClient, agent_id: UUID):
        self.db = db
        self.client = client
        self.agent_id = agent_id

    @staticmethod
    def _parse_price(value: Any) -> Decimal | None:
        parsed = coerce_number(value)
        if parsed is None:
            return None
        return Decimal(str(parsed))

    async def sync(self, *, modificate: int | None) -> dict[str, int]:
        synced_at = datetime.now(timezone.utc)
        commodities = await self.client.list_all_commodities(per_page=100, modificate=modificate)
        commodities_synced = 0

        for commodity in commodities:
            if not isinstance(commodity, dict):
                continue
            try:
                external_id = int(commodity.get("id"))
            except (TypeError, ValueError):
                continue

            title = commodity.get("title") or commodity.get("name") or f"Commodity {external_id}"
            description = commodity.get("description")
            category = commodity.get("category")
            article = commodity.get("article")

            stmt = insert(SqnsCommodity).values(
                id=uuid4(),
                agent_id=self.agent_id,
                external_id=external_id,
                title=str(title),
                description=str(description).strip() if description is not None else None,
                category=str(category).strip() if category is not None else None,
                price=self._parse_price(commodity.get("price")),
                article=str(article).strip() if article is not None else None,
                raw_data=commodity,
                synced_at=synced_at,
                created_at=synced_at,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_sqns_commodities_agent_external",
                set_={
                    "title": stmt.excluded.title,
                    "description": stmt.excluded.description,
                    "category": stmt.excluded.category,
                    "price": stmt.excluded.price,
                    "article": stmt.excluded.article,
                    "raw_data": stmt.excluded.raw_data,
                    "synced_at": stmt.excluded.synced_at,
                    "updated_at": synced_at,
                },
            )
            await self.db.execute(stmt)
            commodities_synced += 1

        logger.info(
            "sqns_sync_commodities_completed",
            agent_id=str(self.agent_id),
            commodities_synced=commodities_synced,
            modificate=modificate,
        )
        return {"commodities_synced": commodities_synced}
