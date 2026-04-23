from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.services.runtime.neo4j_client import get_neo4j_driver
from app.services.script_flow_graphrag_schema import ScriptFlowGraphPreview

logger = structlog.get_logger(__name__)


async def load_script_flow_graphrag_preview_from_neo4j(
    *,
    tenant_id: UUID,
    agent_id: UUID,
    flow_id: UUID,
    fallback_flow_version: int = 0,
) -> ScriptFlowGraphPreview | None:
    settings = get_settings()
    if not settings.neo4j_enabled:
        return None

    driver = get_neo4j_driver()
    if driver is None:
        return None

    tenant_id_s = str(tenant_id)
    agent_id_s = str(agent_id)
    flow_id_s = str(flow_id)
    database = settings.neo4j_database or None

    node_cypher = """
    MATCH (n:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id})
    RETURN n
    ORDER BY coalesce(n.node_kind, ''), coalesce(n.title, ''), coalesce(n.graph_node_id, '')
    """
    relation_cypher = """
    MATCH (s:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id})
          -[r:GRAPH_RELATION {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id}]->
          (t:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id})
    RETURN r
    ORDER BY coalesce(r.relation_type, ''), coalesce(r.source_graph_node_id, ''), coalesce(r.target_graph_node_id, '')
    """
    community_cypher = """
    MATCH (c:GraphCommunity {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id})
    RETURN c
    ORDER BY coalesce(c.community_key, '')
    """
    diagnostic_cypher = """
    MATCH (d:GraphDiagnostic {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id})
    RETURN d
    LIMIT 1
    """

    params = {
        "tenant_id": tenant_id_s,
        "agent_id": agent_id_s,
        "flow_id": flow_id_s,
    }

    try:
        with driver.session(database=database) as session:
            node_rows = list(session.run(node_cypher, params))
            relation_rows = list(session.run(relation_cypher, params))
            community_rows = list(session.run(community_cypher, params))
            diagnostic_row = session.run(diagnostic_cypher, params).single()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "script_flow_graphrag_neo4j_preview_read_failed",
            flow_id=flow_id_s,
            error=str(exc),
        )
        return None

    if not node_rows and not relation_rows and not community_rows and diagnostic_row is None:
        return None

    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    communities: list[dict[str, Any]] = []
    flow_version = int(fallback_flow_version or 0)

    for row in node_rows:
        node = row.get("n")
        if node is None:
            continue
        flow_version = int(node.get("flow_version") or flow_version or 0)
        nodes.append(
            {
                "graph_node_id": str(node.get("graph_node_id") or ""),
                "node_kind": str(node.get("node_kind") or "entity"),
                "entity_type": str(node.get("entity_type") or ""),
                "title": str(node.get("title") or ""),
                "description": node.get("description"),
                "source_node_ids": list(node.get("source_node_ids") or []),
                "properties": dict(node.get("properties") or {}),
                "community_key": node.get("community_key"),
            }
        )

    for row in relation_rows:
        rel = row.get("r")
        if rel is None:
            continue
        relations.append(
            {
                "source_graph_node_id": str(rel.get("source_graph_node_id") or ""),
                "target_graph_node_id": str(rel.get("target_graph_node_id") or ""),
                "relation_type": str(rel.get("relation_type") or ""),
                "weight": float(rel.get("weight") or 1.0),
                "properties": dict(rel.get("properties") or {}),
            }
        )

    for row in community_rows:
        community = row.get("c")
        if community is None:
            continue
        flow_version = int(community.get("flow_version") or flow_version or 0)
        communities.append(
            {
                "community_key": str(community.get("community_key") or ""),
                "title": str(community.get("title") or ""),
                "summary": community.get("summary"),
                "node_ids": list(community.get("node_ids") or []),
                "properties": dict(community.get("properties") or {}),
            }
        )

    diagnostic_payload: dict[str, Any] | None = None
    if diagnostic_row is not None:
        diagnostic = diagnostic_row.get("d")
        if diagnostic is not None:
            flow_version = int(diagnostic.get("flow_version") or flow_version or 0)
            diagnostic_payload = {
                "flow_version": int(diagnostic.get("flow_version") or flow_version or 0),
                "extraction_model": diagnostic.get("extraction_model"),
                "summary_model": diagnostic.get("summary_model"),
                "extraction_mode": diagnostic.get("extraction_mode"),
                "llm_ok_nodes": int(diagnostic.get("llm_ok_nodes") or 0),
                "llm_failed_nodes": int(diagnostic.get("llm_failed_nodes") or 0),
                "entity_count": int(diagnostic.get("entity_count") or 0),
                "relation_count": int(diagnostic.get("relation_count") or 0),
                "community_count": int(diagnostic.get("community_count") or len(communities)),
                "summary_llm_count": int(diagnostic.get("summary_llm_count") or 0),
                "summary_fallback_count": int(diagnostic.get("summary_fallback_count") or 0),
                "raw": dict(diagnostic.get("debug") or {}),
            }

    return ScriptFlowGraphPreview(
        flow_id=flow_id,
        flow_version=flow_version,
        nodes=nodes,
        relations=relations,
        communities=communities,
        debug={
            "source": "neo4j",
            "diagnostic": diagnostic_payload,
        },
    )
