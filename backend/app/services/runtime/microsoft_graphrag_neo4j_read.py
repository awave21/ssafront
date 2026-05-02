from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.services.runtime.neo4j_client import get_neo4j_driver

logger = structlog.get_logger(__name__)


async def search_microsoft_graphrag_neo4j(
    *,
    tenant_id: UUID,
    agent_id: UUID,
    query_tokens: list[str],
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    settings = get_settings()
    if not settings.neo4j_enabled:
        return [], [], "neo4j_disabled"

    driver = get_neo4j_driver()
    if driver is None:
        return [], [], "neo4j_unavailable"

    tokens = [str(token).strip().lower() for token in query_tokens if str(token).strip()]
    if not tokens:
        return [], [], "neo4j_empty_query"

    cypher = """
    MATCH (n:MicrosoftGraphNode {tenant_id: $tenant_id, agent_id: $agent_id})
    OPTIONAL MATCH (n)-[r:MICROSOFT_GRAPH_RELATION {tenant_id: $tenant_id, agent_id: $agent_id}]-(m:MicrosoftGraphNode {tenant_id: $tenant_id, agent_id: $agent_id})
    WITH n,
         collect(DISTINCT r.label)[0..6] AS relation_labels,
         collect(DISTINCT m.label)[0..6] AS neighbor_labels,
         toLower(
           coalesce(n.label, '') + ' ' +
           coalesce(n.description, '') + ' ' +
           coalesce(n.entity_type, '')
         ) AS hay
    WITH n, relation_labels, neighbor_labels, hay,
         reduce(score = 0.0, token IN $tokens |
           score + CASE WHEN hay CONTAINS token THEN 1.0 ELSE 0.0 END
         ) AS token_hits
    WHERE token_hits > 0
    RETURN n, relation_labels, neighbor_labels,
           (token_hits / toFloat(size($tokens))) AS score
    ORDER BY score DESC, size(neighbor_labels) DESC, size(relation_labels) DESC, n.label ASC
    LIMIT $limit
    """

    params = {
        "tenant_id": str(tenant_id),
        "agent_id": str(agent_id),
        "tokens": tokens,
        "limit": max(1, int(limit or 5)),
    }
    database = settings.neo4j_database or None

    try:
        with driver.session(database=database) as session:
            rows = list(session.run(cypher, params))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "microsoft_graphrag_neo4j_read_failed",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            error=str(exc),
        )
        return [], [], "neo4j_error"

    matches: list[dict[str, Any]] = []
    snippets: list[dict[str, Any]] = []
    for row in rows:
        node = row.get("n")
        if node is None:
            continue
        description = str(node.get("description") or "").strip()
        match = {
            "name": str(node.get("label") or node.get("graph_node_id") or ""),
            "score": round(float(row.get("score") or 0.0), 4),
            "entity_type": str(node.get("entity_type") or "entity"),
            "graph_node_id": str(node.get("graph_node_id") or ""),
            "excerpt": description[:260] if description else None,
            "neighbor_titles": [str(v) for v in (row.get("neighbor_labels") or []) if str(v).strip()],
            "relation_labels": [str(v) for v in (row.get("relation_labels") or []) if str(v).strip()],
        }
        matches.append(match)
        if description:
            snippets.append(
                {
                    "title": match["name"],
                    "excerpt": description[:260],
                    "graph_node_id": match["graph_node_id"],
                }
            )

    return matches, snippets, ("neo4j_graph" if matches else "neo4j_empty")
