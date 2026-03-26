from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsVisit

_CHUNK_SIZE = 500


def _chunked(values: list[Any], size: int) -> Iterable[list[Any]]:
    for idx in range(0, len(values), size):
        yield values[idx : idx + size]


class PrimaryVisitRecalculator:
    def __init__(self, db: AsyncSession, agent_id: UUID):
        self.db = db
        self.agent_id = agent_id

    async def recalculate_for_clients(self, client_external_ids: Iterable[int]) -> int:
        normalized_ids = sorted({int(item) for item in client_external_ids if item is not None})
        if not normalized_ids:
            return 0

        now = datetime.now(timezone.utc)
        primary_visit_ids: set[UUID] = set()

        for id_chunk in _chunked(normalized_ids, _CHUNK_SIZE):
            ranked_subquery = (
                select(
                    SqnsVisit.id.label("visit_id"),
                    func.row_number()
                    .over(
                        partition_by=SqnsVisit.client_external_id,
                        order_by=(SqnsVisit.visit_datetime.asc(), SqnsVisit.external_id.asc()),
                    )
                    .label("visit_rank"),
                )
                .where(
                    SqnsVisit.agent_id == self.agent_id,
                    SqnsVisit.client_external_id.in_(id_chunk),
                    SqnsVisit.deleted.is_(False),
                    SqnsVisit.visit_datetime.is_not(None),
                )
                .subquery()
            )
            primary_ids_stmt = select(ranked_subquery.c.visit_id).where(ranked_subquery.c.visit_rank == 1)
            rows = (await self.db.execute(primary_ids_stmt)).scalars().all()
            primary_visit_ids.update(rows)

            reset_stmt = (
                update(SqnsVisit)
                .where(
                    SqnsVisit.agent_id == self.agent_id,
                    SqnsVisit.client_external_id.in_(id_chunk),
                )
                .values(is_primary_visit=False, updated_at=now)
            )
            await self.db.execute(reset_stmt)

        if primary_visit_ids:
            for id_chunk in _chunked(list(primary_visit_ids), _CHUNK_SIZE):
                mark_primary_stmt = (
                    update(SqnsVisit)
                    .where(
                        SqnsVisit.agent_id == self.agent_id,
                        SqnsVisit.id.in_(id_chunk),
                    )
                    .values(is_primary_visit=True, updated_at=now)
                )
                await self.db.execute(mark_primary_stmt)

        return len(normalized_ids)
