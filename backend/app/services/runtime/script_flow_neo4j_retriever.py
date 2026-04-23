from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.services.runtime.neo4j_client import get_neo4j_driver


@dataclass
class ScriptFlowNeo4jContextPacket:
    query: str
    matches: list[dict[str, Any]] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)


class ScriptFlowNeo4jRetriever:
    """Neo4j-backed graph retriever for tenant/agent scoped ScriptFlow GraphRAG."""

    def __init__(
        self,
        *,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> None:
        self.tenant_id = str(tenant_id)
        self.agent_id = str(agent_id)

    async def build_context_packet(
        self,
        *,
        query: str,
        stage: str | None = None,
        service_id: str | None = None,
        limit: int = 6,
    ) -> ScriptFlowNeo4jContextPacket:
        driver = get_neo4j_driver()
        settings = get_settings()
        if driver is None:
            return ScriptFlowNeo4jContextPacket(
                query=query,
                matches=[],
                debug={
                    "engine": "neo4j_graph_first",
                    "search_mode": "disabled",
                    "neo4j_available": False,
                },
            )

        tokens = [t.strip().lower() for t in query.split() if len(t.strip()) >= 3][:8]
        if not tokens:
            return ScriptFlowNeo4jContextPacket(
                query=query,
                matches=[],
                debug={
                    "engine": "neo4j_graph_first",
                    "search_mode": "empty_query",
                    "neo4j_available": True,
                },
            )

        cypher = """
        MATCH (n:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id})
        OPTIONAL MATCH (n)-[:IN_COMMUNITY {tenant_id: $tenant_id, agent_id: $agent_id}]->(c:GraphCommunity {tenant_id: $tenant_id, agent_id: $agent_id})
        OPTIONAL MATCH (n)-[r:GRAPH_RELATION {tenant_id: $tenant_id, agent_id: $agent_id}]-(m:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id})
        WITH n, c,
             collect(DISTINCT type(r)) AS relation_types,
             collect(DISTINCT m.title)[0..6] AS neighbor_titles,
             toLower(
               coalesce(n.title, '') + ' ' +
               coalesce(n.description, '') + ' ' +
               coalesce(n.entity_type, '') + ' ' +
               coalesce(n.node_kind, '') + ' ' +
               coalesce(c.title, '') + ' ' +
               coalesce(c.summary, '')
             ) AS hay
        WITH n, c, relation_types, neighbor_titles, hay,
             reduce(score = 0.0, token IN $tokens |
               score + CASE WHEN hay CONTAINS token THEN 1.0 ELSE 0.0 END
             ) AS token_hits
        WHERE token_hits > 0
          AND ($stage IS NULL OR coalesce(n.properties.stage, '') = $stage OR n.entity_type = 'stage')
        RETURN n, c, relation_types, neighbor_titles,
               (token_hits / toFloat(size($tokens))) +
               CASE WHEN n.node_kind = 'canvas' THEN 0.08 ELSE 0.03 END +
               CASE WHEN c IS NULL THEN 0.0 ELSE 0.08 END AS score
        ORDER BY score DESC
        LIMIT $limit
        """

        params = {
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "tokens": tokens,
            "stage": stage,
            "limit": max(1, limit),
        }

        try:
            database = settings.neo4j_database or None
            with driver.session(database=database) as session:
                result = session.run(cypher, params)
                rows = list(result)
        except Exception as exc:  # noqa: BLE001
            return ScriptFlowNeo4jContextPacket(
                query=query,
                matches=[],
                debug={
                    "engine": "neo4j_graph_first",
                    "search_mode": "error",
                    "neo4j_available": True,
                    "error": str(exc),
                },
            )

        matches: list[dict[str, Any]] = []
        for row in rows:
            node = row.get("n")
            community = row.get("c")
            if node is None:
                continue
            source_node_ids = list(node.get("source_node_ids") or [])
            node_id = source_node_ids[0] if source_node_ids else str(node.get("graph_node_id") or "")
            if service_id:
                raw_service_ids = (node.get("properties") or {}).get("service_ids")
                if isinstance(raw_service_ids, list) and service_id not in [str(v) for v in raw_service_ids]:
                    continue
            matches.append(
                {
                    "flow_id": str(node.get("flow_id") or ""),
                    "node_id": node_id,
                    "graph_node_id": str(node.get("graph_node_id") or ""),
                    "node_type": (node.get("properties") or {}).get("node_type") or node.get("entity_type"),
                    "title": str(node.get("title") or ""),
                    "score": float(row.get("score") or 0.0),
                    "stage": (node.get("properties") or {}).get("stage"),
                    "content_text": node.get("description"),
                    "metadata": {
                        "graph_node_kind": node.get("node_kind"),
                        "graph_entity_type": node.get("entity_type"),
                        "community_key": node.get("community_key"),
                        "graph_relation_types": list(row.get("relation_types") or []),
                        "neighbor_titles": list(row.get("neighbor_titles") or []),
                        "community_title": community.get("title") if community else None,
                        "community_summary": community.get("summary") if community else None,
                        "recommended_next_step": (
                            (community.get("properties") or {}).get("recommended_next_step") if community else None
                        ),
                    },
                    "neighbors": [],
                }
            )

        return ScriptFlowNeo4jContextPacket(
            query=query,
            matches=matches,
            debug={
                "engine": "neo4j_graph_first",
                "search_mode": "cypher_token_rank",
                "neo4j_available": True,
                "graph_matches": len(matches),
                "stage": stage,
                "service_id": service_id,
            },
        )

