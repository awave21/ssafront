from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsVisit
from app.services.sqns.client import SQNSClient
from app.services.sqns.primary_visit_recalculator import PrimaryVisitRecalculator
from app.services.sqns.sync_handlers.common import parse_bool, parse_datetime, parse_decimal, parse_int
from app.services.sqns.sync_handlers.visit_commodity_lines import replace_visit_payload_commodity_lines

logger = structlog.get_logger(__name__)
_EXTERNAL_IDS_BATCH_SIZE = 1000


def _chunked(values: list[int], size: int) -> Iterable[list[int]]:
    for idx in range(0, len(values), size):
        yield values[idx : idx + size]


def _extract_client_external_id(visit: dict[str, Any]) -> int | None:
    direct_client_value = parse_int(
        visit.get("clientId")
        or visit.get("client_id")
        or visit.get("client")
        or visit.get("patientId")
        or visit.get("patient_id")
    )
    if direct_client_value is not None:
        return direct_client_value

    nested_candidates = (visit.get("clientData"), visit.get("client"))
    for candidate in nested_candidates:
        if not isinstance(candidate, dict):
            continue
        nested_value = parse_int(
            candidate.get("id")
            or candidate.get("clientId")
            or candidate.get("client_id")
            or candidate.get("patientId")
            or candidate.get("patient_id")
        )
        if nested_value is not None:
            return nested_value

    return None


def _sqns_visit_datetime_raw(visit: dict[str, Any]) -> Any:
    """По API SQNS момент приёма задаётся полем datetime у объекта визита (ещё встречается dateTime)."""
    v = visit.get("datetime") or visit.get("dateTime")
    if v is not None:
        return v
    inner = visit.get("visit")
    if isinstance(inner, dict):
        return inner.get("datetime") or inner.get("dateTime")
    return None


def sqns_visit_datetime_raw_string(visit: dict[str, Any] | None) -> str | None:
    """Строка поля datetime из ответа SQNS (как пришла), для отображения без пересчёта TZ."""
    if not isinstance(visit, dict):
        return None
    raw = _sqns_visit_datetime_raw(visit)
    if isinstance(raw, str):
        s = raw.strip()
        return s or None
    return None


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
        parsed_visits: list[tuple[dict[str, Any], int]] = []

        for visit in visits:
            if not isinstance(visit, dict):
                continue
            external_id = parse_int(visit.get("id"))
            if external_id is None:
                continue
            parsed_visits.append((visit, external_id))

        existing_client_by_visit_external_id: dict[int, int] = {}
        if parsed_visits:
            parsed_external_ids = [external_id for _, external_id in parsed_visits]
            for ids_chunk in _chunked(parsed_external_ids, _EXTERNAL_IDS_BATCH_SIZE):
                existing_stmt = select(
                    SqnsVisit.external_id,
                    SqnsVisit.client_external_id,
                ).where(
                    SqnsVisit.agent_id == self.agent_id,
                    SqnsVisit.external_id.in_(ids_chunk),
                )
                existing_rows = (await self.db.execute(existing_stmt)).all()
                for row in existing_rows:
                    if row[1] is None:
                        continue
                    existing_client_by_visit_external_id[int(row[0])] = int(row[1])

        affected_client_external_ids: set[int] = set()
        for visit, external_id in parsed_visits:
            client_external_id = _extract_client_external_id(visit)
            previous_client_id = existing_client_by_visit_external_id.get(external_id)
            if previous_client_id is not None:
                affected_client_external_ids.add(previous_client_id)
            if client_external_id is not None:
                affected_client_external_ids.add(client_external_id)

            stmt = insert(SqnsVisit).values(
                id=uuid4(),
                agent_id=self.agent_id,
                external_id=external_id,
                resource_external_id=parse_int(visit.get("resourceId")),
                client_external_id=client_external_id,
                visit_datetime=parse_datetime(_sqns_visit_datetime_raw(visit)),
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
            await replace_visit_payload_commodity_lines(
                self.db,
                agent_id=self.agent_id,
                visit_external_id=external_id,
                visit_raw=visit,
            )
            visits_synced += 1

        primary_clients_recalculated = 0
        if affected_client_external_ids:
            recalculator = PrimaryVisitRecalculator(self.db, self.agent_id)
            primary_clients_recalculated = await recalculator.recalculate_for_clients(affected_client_external_ids)

        logger.info(
            "sqns_sync_visits_completed",
            agent_id=str(self.agent_id),
            visits_synced=visits_synced,
            primary_clients_recalculated=primary_clients_recalculated,
            modificate=modificate,
            date_from=date_from,
            date_till=date_till,
        )
        return {
            "visits_synced": visits_synced,
            "primary_clients_recalculated": primary_clients_recalculated,
        }
