from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.script_flow_graph_community import ScriptFlowGraphCommunity
from app.db.models.script_flow_graph_node import ScriptFlowGraphNode
from app.db.models.script_flow_graph_relation import ScriptFlowGraphRelation
from app.services.directory.service import create_embedding


@dataclass
class ScriptFlowGraphContextPacket:
    query: str
    matches: list[dict[str, Any]] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)


class ScriptFlowGraphRAGRetriever:
    """Graph-first runtime retriever over stored GraphRAG nodes/communities."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        agent_id: UUID,
        openai_api_key: str | None = None,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.openai_api_key = openai_api_key

    async def build_context_packet(
        self,
        *,
        query: str,
        stage: str | None = None,
        service_id: str | None = None,
        limit: int = 6,
    ) -> ScriptFlowGraphContextPacket:
        tokens = self._tokens(query)
        if not tokens:
            return ScriptFlowGraphContextPacket(
                query=query,
                matches=[],
                debug={
                    "engine": "graphrag_graph_first",
                    "search_mode": "empty_query",
                    "graph_matches": 0,
                },
            )

        filters = [
            ScriptFlowGraphNode.tenant_id == self.tenant_id,
            ScriptFlowGraphNode.agent_id == self.agent_id,
        ]
        if stage:
            filters.append(
                or_(
                    ScriptFlowGraphNode.entity_type == "stage",
                    ScriptFlowGraphNode.properties["stage"].astext == stage,
                )
            )

        rows = (
            await self.db.execute(
                select(ScriptFlowGraphNode).where(*filters)
            )
        ).scalars().all()

        community_rows = (
            await self.db.execute(
                select(ScriptFlowGraphCommunity).where(
                    ScriptFlowGraphCommunity.tenant_id == self.tenant_id,
                    ScriptFlowGraphCommunity.agent_id == self.agent_id,
                )
            )
        ).scalars().all()

        query_embedding = None
        if self.openai_api_key:
            query_embedding = await create_embedding(
                query,
                openai_api_key=self.openai_api_key,
                db=self.db,
                tenant_id=self.tenant_id,
                charge_source_type="embedding.script_flow_graphrag_query",
                charge_metadata={"agent_id": str(self.agent_id)},
            )

        scored: list[tuple[float, ScriptFlowGraphNode]] = []
        for row in rows:
            community = next((c for c in community_rows if str(c.community_key) == str(row.community_key or "")), None)
            hay = " ".join(
                [
                    str(row.title or ""),
                    str(row.description or ""),
                    str((row.properties or {}).get("node_type") or ""),
                    str((row.properties or {}).get("stage") or ""),
                    str(community.title if community else ""),
                    str(community.summary if community else ""),
                    " ".join(str(v) for v in (((community.properties or {}).get("key_points") or []) if community else [])),
                ]
            ).lower()
            if service_id:
                raw_service_ids = (row.properties or {}).get("service_ids")
                if isinstance(raw_service_ids, list) and service_id not in [str(v) for v in raw_service_ids]:
                    continue
            token_hits = sum(1 for t in tokens if t in hay)
            semantic_score = 0.0
            if query_embedding is not None:
                # semantic-lite approximation without persistent graph vectors:
                # reuse overlap + dense prior from rich textual fields.
                dense_text = " ".join(filter(None, [str(row.title or ""), str(row.description or ""), str(community.summary if community else "")])).strip()
                if dense_text:
                    dense_hits = sum(1 for t in tokens if t in dense_text.lower())
                    semantic_score = min(0.35, 0.08 * dense_hits)

            if token_hits <= 0 and semantic_score <= 0:
                continue
            base = token_hits / max(1, len(tokens))
            kind_boost = 0.08 if row.node_kind == "canvas" else 0.03
            community_boost = 0.05 if row.community_key else 0.0
            summary_boost = 0.04 if community and community.summary else 0.0
            scored.append((round(base + semantic_score + kind_boost + community_boost + summary_boost, 4), row))

        scored.sort(key=lambda item: item[0], reverse=True)
        top_rows = [row for _score, row in scored[: max(1, limit)]]
        if not top_rows:
            return ScriptFlowGraphContextPacket(
                query=query,
                matches=[],
                debug={
                    "engine": "graphrag_graph_first",
                    "search_mode": "no_matches",
                    "graph_matches": 0,
                },
            )

        community_keys = {str(r.community_key) for r in top_rows if r.community_key}
        graph_node_ids = {str(r.graph_node_id) for r in top_rows}
        relation_rows = (
            await self.db.execute(
                select(ScriptFlowGraphRelation).where(
                    ScriptFlowGraphRelation.tenant_id == self.tenant_id,
                    ScriptFlowGraphRelation.agent_id == self.agent_id,
                    or_(
                        ScriptFlowGraphRelation.source_graph_node_id.in_(graph_node_ids),
                        ScriptFlowGraphRelation.target_graph_node_id.in_(graph_node_ids),
                    ),
                )
            )
        ).scalars().all()

        community_by_key: dict[str, ScriptFlowGraphCommunity] = {}
        if community_keys:
            community_rows = (
                await self.db.execute(
                    select(ScriptFlowGraphCommunity).where(
                        ScriptFlowGraphCommunity.tenant_id == self.tenant_id,
                        ScriptFlowGraphCommunity.agent_id == self.agent_id,
                        ScriptFlowGraphCommunity.community_key.in_(community_keys),
                    )
                )
            ).scalars().all()
            community_by_key = {str(c.community_key): c for c in community_rows}

        relation_types_by_node: dict[str, list[str]] = defaultdict(list)
        neighbor_ids_by_node: dict[str, list[str]] = defaultdict(list)
        for rel in relation_rows:
            relation_types_by_node[str(rel.source_graph_node_id)].append(str(rel.relation_type))
            relation_types_by_node[str(rel.target_graph_node_id)].append(str(rel.relation_type))
            neighbor_ids_by_node[str(rel.source_graph_node_id)].append(str(rel.target_graph_node_id))
            neighbor_ids_by_node[str(rel.target_graph_node_id)].append(str(rel.source_graph_node_id))

        neighbor_ids = {nid for values in neighbor_ids_by_node.values() for nid in values}
        neighbor_title_map: dict[str, str] = {}
        if neighbor_ids:
            neighbor_rows = (
                await self.db.execute(
                    select(ScriptFlowGraphNode).where(
                        ScriptFlowGraphNode.tenant_id == self.tenant_id,
                        ScriptFlowGraphNode.agent_id == self.agent_id,
                        ScriptFlowGraphNode.graph_node_id.in_(neighbor_ids),
                    )
                )
            ).scalars().all()
            neighbor_title_map = {str(row.graph_node_id): str(row.title) for row in neighbor_rows}

        matches: list[dict[str, Any]] = []
        for score, row in scored[: max(1, limit)]:
            community = community_by_key.get(str(row.community_key or ""))
            node_id = None
            source_ids = [str(v).strip() for v in (row.source_node_ids or []) if str(v).strip()]
            if source_ids:
                node_id = source_ids[0]
            matches.append(
                {
                    "flow_id": str(row.flow_id),
                    "node_id": node_id or str(row.graph_node_id),
                    "graph_node_id": row.graph_node_id,
                    "node_type": (row.properties or {}).get("node_type") or row.entity_type,
                    "title": row.title,
                    "score": score,
                    "stage": (row.properties or {}).get("stage"),
                    "content_text": row.description,
                    "metadata": {
                        "graph_node_kind": row.node_kind,
                        "graph_entity_type": row.entity_type,
                        "community_key": row.community_key,
                        "graph_relation_types": relation_types_by_node.get(str(row.graph_node_id), []),
                        "neighbor_titles": [
                            neighbor_title_map[nid]
                            for nid in neighbor_ids_by_node.get(str(row.graph_node_id), [])[:6]
                            if nid in neighbor_title_map
                        ],
                        "community_title": community.title if community else None,
                        "community_summary": community.summary if community else None,
                        "recommended_next_step": (
                            (community.properties or {}).get("recommended_next_step") if community else None
                        ),
                    },
                    "neighbors": [],
                }
            )

        return ScriptFlowGraphContextPacket(
            query=query,
            matches=matches,
            debug={
                "engine": "graphrag_graph_first",
                "search_mode": "graph_keyword",
                "semantic_lite_used": bool(query_embedding is not None),
                "graph_matches": len(matches),
                "stage": stage,
                "service_id": service_id,
            },
        )

    @staticmethod
    def _tokens(query: str) -> list[str]:
        raw = [t.strip().lower() for t in query.split() if t.strip()]
        out: list[str] = []
        seen: set[str] = set()
        for token in raw:
            if len(token) < 3:
                continue
            if token in seen:
                continue
            seen.add(token)
            out.append(token)
        return out[:8]
