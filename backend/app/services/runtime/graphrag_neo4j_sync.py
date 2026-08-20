from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.db.models.agent import Agent
from app.services.graphrag_export.graphrag_preview import (
    agent_graphrag_workspace,
    load_graphrag_preview_from_workspace,
)
from app.services.runtime.neo4j_client import get_neo4j_driver

logger = structlog.get_logger(__name__)


async def build_graphrag_sync_plan(
    *,
    settings: Any,
    agent: Agent,
    tenant_id: UUID,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    ws = agent_graphrag_workspace(cfg, tenant_id=tenant_id, agent=agent)
    if ws is None or not ws.is_dir():
        return {
            "tenant_id": str(tenant_id),
            "agent_id": str(agent.id),
            "workspace_ready": False,
            "preview_source": "no_workspace",
            "nodes_total": 0,
            "relations_total": 0,
        }

    payload = load_graphrag_preview_from_workspace(ws, max_nodes=None, max_edges=None)
    return {
        "tenant_id": str(tenant_id),
        "agent_id": str(agent.id),
        "workspace_ready": str(payload.get("preview_source") or "") == "workspace_parquet",
        "preview_source": str(payload.get("preview_source") or "unknown"),
        "preview_error": payload.get("preview_error"),
        "nodes_total": int(payload.get("node_count") or 0),
        "relations_total": int(payload.get("edge_count") or 0),
    }


def read_graphrag_neo4j_counts(*, tenant_id: UUID, agent_id: UUID) -> dict[str, Any]:
    settings = get_settings()
    if not settings.neo4j_enabled:
        return {
            "enabled": False,
            "available": False,
            "nodes_total": 0,
            "relations_total": 0,
        }

    driver = get_neo4j_driver()
    if driver is None:
        return {
            "enabled": True,
            "available": False,
            "nodes_total": 0,
            "relations_total": 0,
            "error": "driver_not_initialized",
        }

    tenant_id_s = str(tenant_id)
    agent_id_s = str(agent_id)
    database = settings.neo4j_database or None
    try:
        with driver.session(database=database) as session:
            node_row = session.run(
                """
                MATCH (n:MicrosoftGraphNode {tenant_id: $tenant_id, agent_id: $agent_id})
                RETURN count(n) AS total
                """,
                tenant_id=tenant_id_s,
                agent_id=agent_id_s,
            ).single()
            rel_row = session.run(
                """
                MATCH (:MicrosoftGraphNode {tenant_id: $tenant_id, agent_id: $agent_id})
                      -[r:MICROSOFT_GRAPH_RELATION {tenant_id: $tenant_id, agent_id: $agent_id}]->
                      (:MicrosoftGraphNode {tenant_id: $tenant_id, agent_id: $agent_id})
                RETURN count(r) AS total
                """,
                tenant_id=tenant_id_s,
                agent_id=agent_id_s,
            ).single()
        return {
            "enabled": True,
            "available": True,
            "nodes_total": int(node_row["total"] if node_row else 0),
            "relations_total": int(rel_row["total"] if rel_row else 0),
            "database": database or "default",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "enabled": True,
            "available": False,
            "nodes_total": 0,
            "relations_total": 0,
            "database": database or "default",
            "error": str(exc),
        }


async def sync_graphrag_workspace_to_neo4j(
    *,
    settings: Any,
    agent: Agent,
    tenant_id: UUID,
) -> tuple[bool, str]:
    cfg = settings or get_settings()
    if not cfg.neo4j_enabled:
        return True, "neo4j_disabled"

    driver = get_neo4j_driver()
    if driver is None:
        return False, "Neo4j driver is not initialized"

    ws = agent_graphrag_workspace(cfg, tenant_id=tenant_id, agent=agent)
    if ws is None or not ws.is_dir():
        return False, "GraphRAG workspace is not available"

    payload = load_graphrag_preview_from_workspace(ws, max_nodes=None, max_edges=None)
    preview_source = str(payload.get("preview_source") or "unknown")
    preview_error = payload.get("preview_error")
    if preview_error:
        return False, str(preview_error)
    if preview_source != "workspace_parquet":
        return False, f"GraphRAG preview source is not ready for Neo4j sync: {preview_source}"

    node_rows = [row for row in (payload.get("nodes") or []) if isinstance(row, dict)]
    relation_rows = [row for row in (payload.get("relations") or []) if isinstance(row, dict)]

    tenant_id_s = str(tenant_id)
    agent_id_s = str(agent.id)
    database = cfg.neo4j_database or None

    def _write(tx: Any) -> None:
        tx.run(
            """
            MATCH (n:MicrosoftGraphNode {tenant_id: $tenant_id, agent_id: $agent_id}) DETACH DELETE n
            """,
            tenant_id=tenant_id_s,
            agent_id=agent_id_s,
        )
        for node in node_rows:
            tx.run(
                """
                MERGE (n:MicrosoftGraphNode {tenant_id: $tenant_id, agent_id: $agent_id, graph_node_id: $graph_node_id})
                SET n.label = $label,
                    n.entity_type = $entity_type,
                    n.description = $description,
                    n.source = 'microsoft_graphrag_workspace'
                """,
                tenant_id=tenant_id_s,
                agent_id=agent_id_s,
                graph_node_id=str(node.get("id") or ""),
                label=str(node.get("label") or "")[:500],
                entity_type=str(node.get("type") or "entity")[:120],
                description=str(node.get("description") or "")[:4000],
            )
        for rel in relation_rows:
            tx.run(
                """
                MATCH (s:MicrosoftGraphNode {tenant_id: $tenant_id, agent_id: $agent_id, graph_node_id: $source_graph_node_id})
                MATCH (t:MicrosoftGraphNode {tenant_id: $tenant_id, agent_id: $agent_id, graph_node_id: $target_graph_node_id})
                MERGE (s)-[r:MICROSOFT_GRAPH_RELATION {
                    tenant_id: $tenant_id,
                    agent_id: $agent_id,
                    source_graph_node_id: $source_graph_node_id,
                    target_graph_node_id: $target_graph_node_id,
                    label: $label
                }]->(t)
                SET r.source = 'microsoft_graphrag_workspace'
                """,
                tenant_id=tenant_id_s,
                agent_id=agent_id_s,
                source_graph_node_id=str(rel.get("source") or ""),
                target_graph_node_id=str(rel.get("target") or ""),
                label=str(rel.get("label") or "связь")[:200],
            )

    try:
        with driver.session(database=database) as session:
            session.execute_write(_write)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "microsoft_graphrag_neo4j_sync_failed",
            tenant_id=tenant_id_s,
            agent_id=agent_id_s,
            error=str(exc),
        )
        return False, str(exc)

    logger.info(
        "microsoft_graphrag_neo4j_sync_ok",
        tenant_id=tenant_id_s,
        agent_id=agent_id_s,
        nodes=len(node_rows),
        relations=len(relation_rows),
        database=database or "default",
    )
    return True, "ok"
