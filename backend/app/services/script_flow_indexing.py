"""script_flow_indexing.py

Queue worker for ScriptFlow indexing into retrieval tables.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
import json
import structlog
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.script_flow_graph_community import ScriptFlowGraphCommunity
from app.db.models.script_flow_graph_diagnostic import ScriptFlowGraphDiagnostic
from app.db.models.script_flow_graph_node import ScriptFlowGraphNode
from app.db.models.script_flow_graph_relation import ScriptFlowGraphRelation
from app.db.models.script_flow_edge_index import ScriptFlowEdgeIndex
from app.db.models.script_flow import ScriptFlow
from app.db.models.script_flow_node_index import ScriptFlowNodeIndex
from app.services.script_flow_graphrag_compiler import compile_script_flow_graphrag_payload
from app.services.script_flow_index_compiler import compile_script_flow_index_payload
from app.services.directory.service import create_embedding
from app.services.runtime.script_flow_graphrag_neo4j_sync import (
    sync_script_flow_graphrag_to_neo4j,
)
from app.services.tenant_llm_config import get_decrypted_api_key
from app.services.graphrag_export.corpus_dispatch import maybe_auto_dispatch_graphrag_corpus
from app.utils.broadcast import broadcaster

logger = structlog.get_logger(__name__)


def _coerce_embedding_literal(value: object) -> str | None:
    """Return pgvector literal `[f1,f2,...]` suitable for `CAST(:x AS vector)` in raw SQL."""
    if value is None:
        return None
    if isinstance(value, list) and value and all(isinstance(x, (int, float)) for x in value):
        return "[" + ",".join(str(float(x)) for x in value) + "]"
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
        except Exception:
            return None
        if isinstance(parsed, list) and parsed and all(isinstance(x, (int, float)) for x in parsed):
            return "[" + ",".join(str(float(x)) for x in parsed) + "]"
    return None


async def _persist_script_flow_node_embeddings(
    db: AsyncSession,
    *,
    flow_id: UUID,
    nodes: list[ScriptFlowNodeIndex],
) -> None:
    """Persist embeddings using `CAST(... AS vector)` (asyncpg+SQLAlchemy ORM vector binds are flaky)."""
    for node in nodes:
        if not node.is_searchable:
            continue
        emb_lit = getattr(node, "_embedding_literal", None)
        if not isinstance(emb_lit, str) or not emb_lit:
            continue
        # Cast via TEXT first so asyncpg binds the parameter as `text`, not `vector`.
        await db.execute(
            text(
                "UPDATE script_flow_node_indexes "
                "SET embedding = CAST(CAST(:embedding AS TEXT) AS vector) "
                "WHERE flow_id = :flow_id AND node_id = :node_id"
            ),
            {"embedding": emb_lit, "flow_id": flow_id, "node_id": node.node_id},
        )


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


async def _embed_node_indexes(
    db: AsyncSession,
    *,
    flow: ScriptFlow,
    nodes: list[ScriptFlowNodeIndex],
) -> None:
    if not nodes:
        return

    openai_api_key = await get_decrypted_api_key(db, flow.tenant_id)
    if not openai_api_key:
        logger.info(
            "script_flow_index_embedding_skipped_no_tenant_key",
            flow_id=str(flow.id),
            tenant_id=str(flow.tenant_id),
        )
        return

    for node in nodes:
        if not node.is_searchable:
            continue
        source_text = (node.content_text or node.title or "").strip()
        if not source_text:
            continue
        emb = await create_embedding(
            source_text,
            openai_api_key=openai_api_key,
            db=db,
            tenant_id=flow.tenant_id,
            charge_source_type="embedding.script_flow_node",
            charge_source_id=f"{flow.id}:{node.node_id}",
            charge_metadata={
                "agent_id": str(flow.agent_id),
                "flow_id": str(flow.id),
                "node_id": node.node_id,
            },
        )
        emb_lit = _coerce_embedding_literal(emb)
        if emb_lit:
            # Keep ORM flush INSERT-compatible (embedding=NULL), then UPDATE with CAST(...) below.
            setattr(node, "_embedding_literal", emb_lit)


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
        openai_api_key = await get_decrypted_api_key(db, flow.tenant_id)
        settings = get_settings()
        graph_payload = await compile_script_flow_graphrag_payload(
            flow,
            openai_api_key=openai_api_key,
            extraction_model=settings.script_flow_graphrag_extraction_model,
            summary_model=settings.script_flow_graphrag_summary_model,
        )

        # Важно: не вызывать `_embed_node_indexes` и `db.add_all` до удаления старых строк.
        # Иначе autoflush может попытаться INSERT новых `script_flow_node_indexes` раньше DELETE
        # и упереться в UNIQUE(flow_id, node_id).

        await db.execute(delete(ScriptFlowEdgeIndex).where(ScriptFlowEdgeIndex.flow_id == fid))
        await db.execute(delete(ScriptFlowNodeIndex).where(ScriptFlowNodeIndex.flow_id == fid))
        await db.execute(delete(ScriptFlowGraphRelation).where(ScriptFlowGraphRelation.flow_id == fid))
        await db.execute(delete(ScriptFlowGraphNode).where(ScriptFlowGraphNode.flow_id == fid))
        await db.execute(delete(ScriptFlowGraphCommunity).where(ScriptFlowGraphCommunity.flow_id == fid))
        await db.execute(delete(ScriptFlowGraphDiagnostic).where(ScriptFlowGraphDiagnostic.flow_id == fid))
        await db.commit()

        await _embed_node_indexes(db, flow=flow, nodes=index_payload.nodes)

        if index_payload.nodes:
            db.add_all(index_payload.nodes)
        if index_payload.edges:
            db.add_all(index_payload.edges)
        if graph_payload.nodes:
            db.add_all(graph_payload.nodes)
        if graph_payload.relations:
            db.add_all(graph_payload.relations)
        if graph_payload.communities:
            db.add_all(graph_payload.communities)
        if graph_payload.diagnostic is not None:
            db.add(graph_payload.diagnostic)

        await db.flush()
        await _persist_script_flow_node_embeddings(db, flow_id=fid, nodes=index_payload.nodes)

        await sync_script_flow_graphrag_to_neo4j(
            flow=flow,
            payload=graph_payload,
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
