from __future__ import annotations

from typing import Any

import structlog

from app.core.config import get_settings
from app.db.models.script_flow import ScriptFlow
from app.services.runtime.neo4j_client import get_neo4j_driver
from app.services.script_flow_graphrag_compiler import ScriptFlowGraphRAGPayload

logger = structlog.get_logger(__name__)


async def sync_script_flow_graphrag_to_neo4j(
    *,
    flow: ScriptFlow,
    payload: ScriptFlowGraphRAGPayload,
) -> None:
    settings = get_settings()
    if not settings.neo4j_enabled:
        return

    driver = get_neo4j_driver()
    if driver is None:
        logger.warning("neo4j_sync_skipped_no_driver", flow_id=str(flow.id))
        return

    database = settings.neo4j_database or None
    tenant_id = str(flow.tenant_id)
    agent_id = str(flow.agent_id)
    flow_id = str(flow.id)
    flow_version = int(flow.published_version or 0)

    node_rows: list[dict[str, Any]] = [
        {
            "graph_node_id": n.graph_node_id,
            "node_kind": n.node_kind,
            "entity_type": n.entity_type,
            "title": n.title,
            "description": n.description,
            "source_node_ids": n.source_node_ids or [],
            "properties": n.properties or {},
            "community_key": n.community_key,
        }
        for n in payload.nodes
    ]
    relation_rows: list[dict[str, Any]] = [
        {
            "source_graph_node_id": r.source_graph_node_id,
            "target_graph_node_id": r.target_graph_node_id,
            "relation_type": r.relation_type,
            "weight": r.weight,
            "properties": r.properties or {},
        }
        for r in payload.relations
    ]
    community_rows: list[dict[str, Any]] = [
        {
            "community_key": c.community_key,
            "title": c.title,
            "summary": c.summary,
            "node_ids": c.node_ids or [],
            "properties": c.properties or {},
        }
        for c in payload.communities
    ]
    diagnostic_row: dict[str, Any] | None = None
    if payload.diagnostic is not None:
        diagnostic_row = {
            "flow_version": int(payload.diagnostic.flow_version or flow_version),
            "extraction_model": payload.diagnostic.extraction_model,
            "summary_model": payload.diagnostic.summary_model,
            "extraction_mode": payload.diagnostic.extraction_mode,
            "llm_ok_nodes": int(payload.diagnostic.llm_ok_nodes or 0),
            "llm_failed_nodes": int(payload.diagnostic.llm_failed_nodes or 0),
            "entity_count": int(payload.diagnostic.entity_count or 0),
            "relation_count": int(payload.diagnostic.relation_count or 0),
            "community_count": int(payload.diagnostic.community_count or 0),
            "summary_llm_count": int(payload.diagnostic.summary_llm_count or 0),
            "summary_fallback_count": int(payload.diagnostic.summary_fallback_count or 0),
            "debug": payload.diagnostic.debug or {},
        }

    def _write(tx: Any) -> None:
        tx.run(
            """
            MATCH (n:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id}) DETACH DELETE n
            """,
            tenant_id=tenant_id,
            agent_id=agent_id,
            flow_id=flow_id,
        )
        tx.run(
            """
            MATCH (c:GraphCommunity {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id}) DETACH DELETE c
            """,
            tenant_id=tenant_id,
            agent_id=agent_id,
            flow_id=flow_id,
        )
        tx.run(
            """
            MATCH (d:GraphDiagnostic {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id}) DETACH DELETE d
            """,
            tenant_id=tenant_id,
            agent_id=agent_id,
            flow_id=flow_id,
        )
        for node in node_rows:
            tx.run(
                """
                MERGE (n:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, graph_node_id: $graph_node_id})
                SET n.flow_version = $flow_version,
                    n.node_kind = $node_kind,
                    n.entity_type = $entity_type,
                    n.title = $title,
                    n.description = $description,
                    n.source_node_ids = $source_node_ids,
                    n.properties = $properties,
                    n.community_key = $community_key
                """,
                tenant_id=tenant_id,
                agent_id=agent_id,
                flow_id=flow_id,
                flow_version=flow_version,
                **node,
            )
        for community in community_rows:
            tx.run(
                """
                MERGE (c:GraphCommunity {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, community_key: $community_key})
                SET c.flow_version = $flow_version,
                    c.title = $title,
                    c.summary = $summary,
                    c.node_ids = $node_ids,
                    c.properties = $properties
                """,
                tenant_id=tenant_id,
                agent_id=agent_id,
                flow_id=flow_id,
                flow_version=flow_version,
                **community,
            )
        for rel in relation_rows:
            tx.run(
                """
                MATCH (s:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, graph_node_id: $source_graph_node_id})
                MATCH (t:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, graph_node_id: $target_graph_node_id})
                MERGE (s)-[r:GRAPH_RELATION {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, relation_type: $relation_type, source_graph_node_id: $source_graph_node_id, target_graph_node_id: $target_graph_node_id}]->(t)
                SET r.weight = $weight,
                    r.properties = $properties
                """,
                tenant_id=tenant_id,
                agent_id=agent_id,
                flow_id=flow_id,
                **rel,
            )
        for community in community_rows:
            for node_id in community["node_ids"]:
                tx.run(
                    """
                    MATCH (c:GraphCommunity {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, community_key: $community_key})
                    MATCH (n:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, graph_node_id: $graph_node_id})
                    MERGE (n)-[:IN_COMMUNITY {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id}]->(c)
                    """,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    flow_id=flow_id,
                    community_key=community["community_key"],
                    graph_node_id=node_id,
                )
        if diagnostic_row is not None:
            tx.run(
                """
                MERGE (d:GraphDiagnostic {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id})
                SET d.flow_version = $flow_version,
                    d.extraction_model = $extraction_model,
                    d.summary_model = $summary_model,
                    d.extraction_mode = $extraction_mode,
                    d.llm_ok_nodes = $llm_ok_nodes,
                    d.llm_failed_nodes = $llm_failed_nodes,
                    d.entity_count = $entity_count,
                    d.relation_count = $relation_count,
                    d.community_count = $community_count,
                    d.summary_llm_count = $summary_llm_count,
                    d.summary_fallback_count = $summary_fallback_count,
                    d.debug = $debug
                """,
                tenant_id=tenant_id,
                agent_id=agent_id,
                flow_id=flow_id,
                **diagnostic_row,
            )

    try:
        with driver.session(database=database) as session:
            session.execute_write(_write)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "script_flow_graphrag_neo4j_sync_failed",
            flow_id=flow_id,
            error=str(exc),
        )
