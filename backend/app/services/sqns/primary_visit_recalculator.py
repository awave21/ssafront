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

        for id_chunk in _chunked(normalized_ids, _CHUNK_SIZE):
            # --- is_primary_visit: первый визит клиента у агента ---
            ranked_global = (
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
            primary_global_ids: set[UUID] = set(
                (await self.db.execute(
                    select(ranked_global.c.visit_id).where(ranked_global.c.visit_rank == 1)
                )).scalars().all()
            )

            # --- is_primary_per_resource: первый визит клиента у конкретного сотрудника ---
            ranked_per_resource = (
                select(
                    SqnsVisit.id.label("visit_id"),
                    func.row_number()
                    .over(
                        partition_by=(SqnsVisit.client_external_id, SqnsVisit.resource_external_id),
                        order_by=(SqnsVisit.visit_datetime.asc(), SqnsVisit.external_id.asc()),
                    )
                    .label("visit_rank"),
                )
                .where(
                    SqnsVisit.agent_id == self.agent_id,
                    SqnsVisit.client_external_id.in_(id_chunk),
                    SqnsVisit.deleted.is_(False),
                    SqnsVisit.visit_datetime.is_not(None),
                    SqnsVisit.resource_external_id.is_not(None),
                )
                .subquery()
            )
            primary_per_resource_ids: set[UUID] = set(
                (await self.db.execute(
                    select(ranked_per_resource.c.visit_id).where(ranked_per_resource.c.visit_rank == 1)
                )).scalars().all()
            )

            # Сброс обоих флагов
            await self.db.execute(
                update(SqnsVisit)
                .where(
                    SqnsVisit.agent_id == self.agent_id,
                    SqnsVisit.client_external_id.in_(id_chunk),
                )
                .values(is_primary_visit=False, is_primary_per_resource=False, updated_at=now)
            )

            # Проставляем is_primary_visit
            if primary_global_ids:
                for id_chunk_inner in _chunked(list(primary_global_ids), _CHUNK_SIZE):
                    await self.db.execute(
                        update(SqnsVisit)
                        .where(SqnsVisit.agent_id == self.agent_id, SqnsVisit.id.in_(id_chunk_inner))
                        .values(is_primary_visit=True, updated_at=now)
                    )

            # Проставляем is_primary_per_resource
            if primary_per_resource_ids:
                for id_chunk_inner in _chunked(list(primary_per_resource_ids), _CHUNK_SIZE):
                    await self.db.execute(
                        update(SqnsVisit)
                        .where(SqnsVisit.agent_id == self.agent_id, SqnsVisit.id.in_(id_chunk_inner))
                        .values(is_primary_per_resource=True, updated_at=now)
                    )

        return len(normalized_ids)
