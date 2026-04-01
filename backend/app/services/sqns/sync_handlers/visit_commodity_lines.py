from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsVisitCommodityLine
from app.services.sqns.visit_commodity_extraction import (
    VisitCommodityRef,
    extract_commodity_refs_from_payment_payload,
    extract_commodity_refs_from_visit_payload,
)

SOURCE_VISIT_PAYLOAD = "visit"
SOURCE_PAYMENT = "payment"
REF_VISIT_PAYLOAD = "visit_payload"


def _rows_for_refs(
    *,
    agent_id: UUID,
    visit_external_id: int,
    source: str,
    source_ref: str,
    refs: list[VisitCommodityRef],
    synced_at: datetime,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, ref in enumerate(refs):
        rows.append(
            {
                "id": uuid4(),
                "agent_id": agent_id,
                "visit_external_id": visit_external_id,
                "commodity_external_id": ref.commodity_external_id,
                "title": ref.title,
                "quantity": ref.quantity,
                "amount": ref.amount,
                "source": source,
                "source_ref": source_ref,
                "line_index": idx,
                "synced_at": synced_at,
                "created_at": synced_at,
            }
        )
    return rows


async def replace_visit_payload_commodity_lines(
    db: AsyncSession,
    *,
    agent_id: UUID,
    visit_external_id: int,
    visit_raw: dict[str, Any],
) -> None:
    synced_at = datetime.now(timezone.utc)
    refs = extract_commodity_refs_from_visit_payload(visit_raw)
    await db.execute(
        delete(SqnsVisitCommodityLine).where(
            SqnsVisitCommodityLine.agent_id == agent_id,
            SqnsVisitCommodityLine.visit_external_id == visit_external_id,
            SqnsVisitCommodityLine.source == SOURCE_VISIT_PAYLOAD,
            SqnsVisitCommodityLine.source_ref == REF_VISIT_PAYLOAD,
        )
    )
    if not refs:
        return
    for row in _rows_for_refs(
        agent_id=agent_id,
        visit_external_id=visit_external_id,
        source=SOURCE_VISIT_PAYLOAD,
        source_ref=REF_VISIT_PAYLOAD,
        refs=refs,
        synced_at=synced_at,
    ):
        await db.execute(insert(SqnsVisitCommodityLine).values(**row))


async def replace_payment_commodity_lines(
    db: AsyncSession,
    *,
    agent_id: UUID,
    payment_external_id: str,
    visit_external_id: int | None,
    payment_raw: dict[str, Any],
) -> None:
    synced_at = datetime.now(timezone.utc)
    refs = extract_commodity_refs_from_payment_payload(payment_raw)
    await db.execute(
        delete(SqnsVisitCommodityLine).where(
            SqnsVisitCommodityLine.agent_id == agent_id,
            SqnsVisitCommodityLine.source == SOURCE_PAYMENT,
            SqnsVisitCommodityLine.source_ref == payment_external_id,
        )
    )
    if visit_external_id is None or not refs:
        return
    for row in _rows_for_refs(
        agent_id=agent_id,
        visit_external_id=visit_external_id,
        source=SOURCE_PAYMENT,
        source_ref=payment_external_id,
        refs=refs,
        synced_at=synced_at,
    ):
        await db.execute(insert(SqnsVisitCommodityLine).values(**row))
