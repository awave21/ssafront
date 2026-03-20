from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsSyncCursor


class SqnsSyncCursorStore:
    def __init__(self, db: AsyncSession, agent_id: UUID):
        self.db = db
        self.agent_id = agent_id

    async def get(self, entity: str) -> SqnsSyncCursor | None:
        stmt = select(SqnsSyncCursor).where(
            SqnsSyncCursor.agent_id == self.agent_id,
            SqnsSyncCursor.entity == entity,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_modificate(self, entity: str) -> int | None:
        row = await self.get(entity)
        if row is None:
            return None
        return row.modificate_value

    async def upsert(
        self,
        *,
        entity: str,
        modificate_value: int | None = None,
        date_from: date | None = None,
        date_till: date | None = None,
        last_success_at: datetime | None = None,
        state: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.utcnow()
        values: dict[str, Any] = {
            "id": uuid4(),
            "agent_id": self.agent_id,
            "entity": entity,
            "modificate_value": modificate_value,
            "date_from": date_from,
            "date_till": date_till,
            "last_success_at": last_success_at,
            "state": state,
            "created_at": now,
        }
        stmt = insert(SqnsSyncCursor).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_sqns_sync_cursor_agent_entity",
            set_={
                "modificate_value": modificate_value,
                "date_from": date_from,
                "date_till": date_till,
                "last_success_at": last_success_at,
                "state": state,
                "updated_at": now,
            },
        )
        await self.db.execute(stmt)
