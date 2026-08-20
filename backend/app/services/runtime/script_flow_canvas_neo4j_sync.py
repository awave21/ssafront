"""Sync script flow canvas nodes (with embeddings) to Neo4j.

No LLM extraction — raw node content is written directly as FlowNode labels.
Edges are written as NEXT_STEP_TO relationships with branch labels.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.db.models.script_flow import ScriptFlow
from app.db.models.script_flow_edge_index import ScriptFlowEdgeIndex
from app.db.models.script_flow_node_index import ScriptFlowNodeIndex
from app.services.directory.service import create_embeddings_batch
from app.services.runtime.neo4j_client import get_neo4j_driver
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_VECTOR_INDEX_NAME = "flow_node_embedding"
_VECTOR_DIMS = 1536


def _ensure_vector_index(tx: Any) -> None:
    tx.run(
        f"""
        CREATE VECTOR INDEX {_VECTOR_INDEX_NAME} IF NOT EXISTS
        FOR (n:FlowNode) ON (n.embedding)
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {_VECTOR_DIMS},
            `vector.similarity_function`: 'cosine'
        }}}}
        """
    )


def _write_canvas(
    tx: Any,
    *,
    tenant_id: str,
    agent_id: str,
    flow_id: str,
    flow_name: str,
    flow_version: int,
    node_rows: list[dict[str, Any]],
    edge_rows: list[dict[str, Any]],
) -> None:
    tx.run(
        "MATCH (n:FlowNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id}) DETACH DELETE n",
        tenant_id=tenant_id, agent_id=agent_id, flow_id=flow_id,
    )
    for n in node_rows:
        tx.run(
            """
            MERGE (n:FlowNode {
                tenant_id: $tenant_id,
                agent_id:  $agent_id,
                flow_id:   $flow_id,
                node_id:   $node_id
            })
            SET n:Searchable,
                n.flow_version   = $flow_version,
                n.flow_name      = $flow_name,
                n.node_type      = $node_type,
                n.stage          = $stage,
                n.title          = $title,
                n.content_text   = $content_text,
                n.service_ids    = $service_ids,
                n.employee_ids   = $employee_ids,
                n.is_searchable  = $is_searchable,
                n.embedding      = $embedding
            """,
            tenant_id=tenant_id,
            agent_id=agent_id,
            flow_id=flow_id,
            flow_version=flow_version,
            flow_name=flow_name,
            **n,
        )
    for e in edge_rows:
        tx.run(
            """
            MATCH (s:FlowNode {tenant_id: $tenant_id, agent_id: $agent_id,
                               flow_id: $flow_id, node_id: $source_node_id})
            MATCH (t:FlowNode {tenant_id: $tenant_id, agent_id: $agent_id,
                               flow_id: $flow_id, node_id: $target_node_id})
            MERGE (s)-[r:NEXT_STEP_TO {
                tenant_id: $tenant_id, agent_id: $agent_id,
                flow_id: $flow_id,
                source_node_id: $source_node_id,
                target_node_id: $target_node_id
            }]->(t)
            SET r.branch_label = $branch_label
            """,
            tenant_id=tenant_id,
            agent_id=agent_id,
            flow_id=flow_id,
            **e,
        )


async def sync_script_flow_canvas_to_neo4j(
    *,
    flow: ScriptFlow,
    nodes: list[ScriptFlowNodeIndex],
    edges: list[ScriptFlowEdgeIndex],
    db: AsyncSession,
    openai_api_key: str | None,
) -> None:
    settings = get_settings()
    if not settings.neo4j_enabled:
        return

    driver = get_neo4j_driver()
    if driver is None:
        logger.warning("canvas_neo4j_sync_skipped_no_driver", flow_id=str(flow.id))
        return

    tenant_id = str(flow.tenant_id)
    agent_id = str(flow.agent_id)
    flow_id = str(flow.id)
    flow_version = int(flow.published_version or 0)

    # Build parent_title map: для каждой ноды находим её предка по NEXT_STEP_TO.
    # Это даёт «context-aware embedding» — нода знает откуда она по сценарию.
    title_by_node_id: dict[str, str] = {n.node_id: (n.title or "") for n in nodes}
    parent_title_by_node_id: dict[str, str] = {}
    for e in edges:
        # source → target: parent для target — это source
        src_title = title_by_node_id.get(e.source_node_id)
        if src_title and e.target_node_id not in parent_title_by_node_id:
            parent_title_by_node_id[e.target_node_id] = src_title

    flow_name = flow.name or ""

    def _build_enriched_text(node: ScriptFlowNodeIndex) -> str:
        parts: list[str] = []
        if flow_name:
            parts.append(f"Поток: {flow_name}")
        if node.stage:
            parts.append(f"Этап: {node.stage}")
        if node.node_type:
            parts.append(f"Тип ноды: {node.node_type}")
        parent_title = parent_title_by_node_id.get(node.node_id)
        if parent_title:
            parts.append(f"Предыдущий шаг: {parent_title}")
        if node.title:
            parts.append(f"Тема: {node.title}")
        if node.content_text:
            parts.append(node.content_text)
        return "\n".join(parts).strip()

    # Batch all canvas embeddings into one OpenAI request — теперь с обогащённым текстом.
    embedding_texts = [_build_enriched_text(n) for n in nodes]
    embeddings: list[list[float] | None] = (
        await create_embeddings_batch(
            embedding_texts,
            openai_api_key=openai_api_key,
            db=db,
            tenant_id=flow.tenant_id,
            charge_source_type="embedding.script_flow_canvas",
            charge_source_id=str(flow.id),
            charge_metadata={"agent_id": agent_id, "flow_id": flow_id},
        )
        if nodes and openai_api_key
        else [None] * len(nodes)
    )

    node_rows: list[dict[str, Any]] = [
        {
            "node_id": node.node_id,
            "node_type": node.node_type or "",
            "stage": node.stage or "",
            "title": node.title or "",
            "content_text": node.content_text or "",
            "service_ids": list(node.service_ids or []),
            "employee_ids": list(node.employee_ids or []),
            "is_searchable": bool(node.is_searchable),
            "embedding": embeddings[i] if i < len(embeddings) else None,
        }
        for i, node in enumerate(nodes)
    ]

    edge_rows: list[dict[str, Any]] = [
        {
            "source_node_id": e.source_node_id,
            "target_node_id": e.target_node_id,
            "branch_label": e.branch_label or "",
        }
        for e in edges
    ]

    database = settings.neo4j_database or None

    def _write(tx: Any) -> None:
        _write_canvas(
            tx,
            tenant_id=tenant_id,
            agent_id=agent_id,
            flow_id=flow_id,
            flow_name=flow.name or "",
            flow_version=flow_version,
            node_rows=node_rows,
            edge_rows=edge_rows,
        )

    try:
        with driver.session(database=database) as session:
            session.execute_write(_write)
        logger.info(
            "script_flow_canvas_neo4j_synced",
            flow_id=flow_id,
            nodes=len(node_rows),
            edges=len(edge_rows),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "script_flow_canvas_neo4j_sync_failed",
            flow_id=flow_id,
            error=str(exc),
        )
