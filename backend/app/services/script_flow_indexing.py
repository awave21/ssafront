"""script_flow_indexing.py

Queue worker for ScriptFlow indexing into retrieval tables.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.script_flow_edge_index import ScriptFlowEdgeIndex
from app.db.models.script_flow import ScriptFlow
from app.db.models.script_flow_node_index import ScriptFlowNodeIndex
from app.services.script_flow_index_compiler import compile_script_flow_index_payload
from app.services.runtime.script_flow_canvas_neo4j_sync import sync_script_flow_canvas_to_neo4j
from app.services.tenant_llm_config import get_decrypted_api_key
from app.services.graphrag_export.corpus_dispatch import maybe_auto_dispatch_graphrag_corpus
from app.utils.broadcast import broadcaster

logger = structlog.get_logger(__name__)


async def _broadcast_script_flow_index_update(
    *,
    agent_id: UUID,
    flow_id: UUID,
    index_status: str,
    published_version: int,
    index_error: str | None = None,
    index_progress: int | None = None,
) -> None:
    payload = {
        "type": "script_flow_index_updated",
        "data": {
            "agent_id": str(agent_id),
            "flow_id": str(flow_id),
            "index_status": index_status,
            "published_version": int(published_version or 0),
        },
    }
    if index_error is not None:
        payload["data"]["index_error"] = index_error
    if index_progress is not None:
        payload["data"]["index_progress"] = index_progress
    try:
        await broadcaster.publish(agent_id, payload)
    except Exception as exc:
        logger.warning(
            "script_flow_index_broadcast_failed",
            agent_id=str(agent_id),
            flow_id=str(flow_id),
            error=str(exc),
        )


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
        .where(
            ScriptFlow.index_status == "pending",
            ScriptFlow.index_retry_count < 15,
        )
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
            try:
                await db.rollback()
            except Exception:
                pass
            await db.execute(
                update(ScriptFlow)
                .where(ScriptFlow.id == flow.id)
                .values(
                    index_status="failed",
                    index_error=str(exc),
                    index_progress=None,
                    index_retry_count=getattr(flow, "index_retry_count", 0) + 1,
                )
            )
            await db.commit()
            await _broadcast_script_flow_index_update(
                agent_id=flow.agent_id,
                flow_id=flow.id,
                index_status="failed",
                published_version=int(getattr(flow, "published_version", 0) or 0),
                index_error=str(exc),
            )

    return processed


async def _index_flow(db: AsyncSession, flow: ScriptFlow) -> None:
    fid = flow.id

    async def cancel_requested() -> bool:
        flag = (
            await db.execute(
                select(ScriptFlow.index_cancel_requested).where(ScriptFlow.id == fid)
            )
        ).scalar_one_or_none()
        return bool(flag)

    async def abort_if_cancelled() -> bool:
        if not await cancel_requested():
            return False
        await db.execute(
            update(ScriptFlow)
            .where(ScriptFlow.id == fid)
            .values(
                index_status="idle",
                index_error="Индексация отменена",
                index_progress=None,
                index_cancel_requested=False,
            )
        )
        await db.commit()
        await _broadcast_script_flow_index_update(
            agent_id=flow.agent_id,
            flow_id=fid,
            index_status="idle",
            published_version=int(flow.published_version or 0),
            index_error="Индексация отменена",
        )
        return True

    await db.execute(
        update(ScriptFlow)
        .where(ScriptFlow.id == fid)
        .values(index_status="indexing", index_progress=5, index_error=None)
    )
    await db.commit()
    await _broadcast_script_flow_index_update(
        agent_id=flow.agent_id,
        flow_id=fid,
        index_status="indexing",
        published_version=int(flow.published_version or 0),
        index_progress=5,
    )

    if await abort_if_cancelled():
        return

    await db.execute(
        update(ScriptFlow).where(ScriptFlow.id == fid).values(index_progress=55)
    )
    await db.commit()
    if await abort_if_cancelled():
        return

    try:
        index_payload = compile_script_flow_index_payload(flow)

        # Удаляем устаревшие строки перед INSERT, чтобы не упереться в UNIQUE(flow_id, node_id).
        await db.execute(delete(ScriptFlowEdgeIndex).where(ScriptFlowEdgeIndex.flow_id == fid))
        await db.execute(delete(ScriptFlowNodeIndex).where(ScriptFlowNodeIndex.flow_id == fid))
        await db.commit()

        if index_payload.nodes:
            db.add_all(index_payload.nodes)
        if index_payload.edges:
            db.add_all(index_payload.edges)

        await db.flush()
        await db.commit()

        openai_api_key = await get_decrypted_api_key(db, flow.tenant_id)
        await sync_script_flow_canvas_to_neo4j(
            flow=flow,
            nodes=index_payload.nodes,
            edges=index_payload.edges,
            db=db,
            openai_api_key=openai_api_key,
        )

        await db.execute(
            update(ScriptFlow).where(ScriptFlow.id == fid).values(index_progress=96)
        )
        await db.commit()
        if await abort_if_cancelled():
            return

        await db.execute(
            update(ScriptFlow)
            .where(ScriptFlow.id == fid)
            .values(
                index_status="indexed",
                indexed_version=flow.published_version,
                index_error=None,
                index_progress=None,
                last_indexed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
        logger.info("script_flow_indexed", flow_id=str(flow.id))
        await _broadcast_script_flow_index_update(
            agent_id=flow.agent_id,
            flow_id=fid,
            index_status="indexed",
            published_version=int(flow.published_version or 0),
        )
        await maybe_auto_dispatch_graphrag_corpus(flow.agent_id, flow.tenant_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("script_flow_index_failed", flow_id=str(fid), error=str(exc))
        try:
            await db.rollback()
        except Exception:
            pass
        await db.execute(
            update(ScriptFlow)
            .where(ScriptFlow.id == fid)
            .values(
                index_status="failed",
                index_error=str(exc),
                index_progress=None,
                index_retry_count=func.coalesce(ScriptFlow.index_retry_count, 0) + 1,
            )
        )
        await db.commit()
        await _broadcast_script_flow_index_update(
            agent_id=flow.agent_id,
            flow_id=fid,
            index_status="failed",
            published_version=int(flow.published_version or 0),
            index_error=str(exc),
        )
        return
