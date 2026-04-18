"""
script_flow_indexing.py

Background service: picks up ScriptFlow records with index_status='pending'
and indexes their compiled_text into LightRAG.

If LightRAG is not configured (lightrag_enabled=False), the worker loop
simply skips processing. This file must exist so that the lightrag_index
worker can import it even when LightRAG is disabled.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.script_flow import ScriptFlow

logger = structlog.get_logger(__name__)


async def process_pending_script_flow_indexes(
    db: AsyncSession,
    *,
    limit: int = 5,
) -> int:
    """Process up to `limit` ScriptFlow records with index_status='pending'.

    Returns the number of flows processed in this batch.
    """
    stmt = (
        select(ScriptFlow)
        .where(ScriptFlow.index_status == "pending")
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    flows = result.scalars().all()

    if not flows:
        return 0

    processed = 0
    for flow in flows:
        try:
            await _index_flow(db, flow)
            processed += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "script_flow_index_failed",
                flow_id=str(flow.id),
                error=str(exc),
            )
            await db.execute(
                update(ScriptFlow)
                .where(ScriptFlow.id == flow.id)
                .values(index_status="failed", index_error=str(exc))
            )
            await db.commit()

    return processed


async def _index_flow(db: AsyncSession, flow: ScriptFlow) -> None:
    """Index a single ScriptFlow. Placeholder — add LightRAG calls here."""
    await db.execute(
        update(ScriptFlow)
        .where(ScriptFlow.id == flow.id)
        .values(index_status="indexing")
    )
    await db.commit()

    await db.execute(
        update(ScriptFlow)
        .where(ScriptFlow.id == flow.id)
        .values(
            index_status="indexed",
            indexed_version=flow.published_version,
            index_error=None,
            last_indexed_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    logger.info("script_flow_indexed", flow_id=str(flow.id))
