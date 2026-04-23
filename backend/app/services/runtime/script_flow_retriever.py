"""Lightweight retrieval interface for pgvector-based script flow search."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.script_flow_edge_index import ScriptFlowEdgeIndex
from app.db.models.script_flow_node_index import ScriptFlowNodeIndex
from app.services.directory.service import create_embedding


@dataclass
class ScriptFlowNodeHit:
    flow_id: UUID
    node_id: str
    node_type: str
    title: str
    score: float
    stage: str | None = None
    content_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScriptFlowContextPacket:
    query: str
    matches: list[dict[str, Any]] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)


class ScriptFlowRetriever:
    """Interface for graph-aware retrieval over script flow nodes."""

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

    async def search_nodes(
        self,
        *,
        query: str,
        limit: int = 6,
        stage: str | None = None,
        service_id: str | None = None,
        entry_only: bool = False,
    ) -> list[ScriptFlowNodeHit]:
        hits, _debug = await self.search_nodes_with_debug(
            query=query,
            limit=limit,
            stage=stage,
            service_id=service_id,
            entry_only=entry_only,
        )
        return hits

    async def search_nodes_with_debug(
        self,
        *,
        query: str,
        limit: int = 6,
        stage: str | None = None,
        service_id: str | None = None,
        entry_only: bool = False,
    ) -> tuple[list[ScriptFlowNodeHit], dict[str, Any]]:
        """Return node matches via pgvector with lexical fallback.

        Stage is treated as a soft filter: if stage-constrained lookup returns
        nothing, we retry once without stage to avoid losing relevant flows when
        indexed nodes use different stage labels (or no stage at all).
        """
        q = (query or "").strip()
        if not q:
            return [], {
                "search_mode": "empty_query",
                "stage_fallback_used": False,
                "entry_only": entry_only,
            }

        vector_hits = await self._vector_search_nodes(
            query=q,
            limit=limit,
            stage=stage,
            service_id=service_id,
            entry_only=entry_only,
        )
        if vector_hits:
            return vector_hits, {
                "search_mode": "vector_stage_filtered" if stage else "vector",
                "stage_fallback_used": False,
                "entry_only": entry_only,
            }

        lexical_hits = await self._lexical_search_nodes(
            query=q,
            limit=limit,
            stage=stage,
            service_id=service_id,
            entry_only=entry_only,
        )
        if lexical_hits:
            return lexical_hits, {
                "search_mode": "lexical_stage_filtered" if stage else "lexical",
                "stage_fallback_used": False,
                "entry_only": entry_only,
            }

        if stage:
            vector_hits_no_stage = await self._vector_search_nodes(
                query=q,
                limit=limit,
                stage=None,
                service_id=service_id,
                entry_only=entry_only,
            )
            if vector_hits_no_stage:
                return vector_hits_no_stage, {
                    "search_mode": "vector_stage_fallback",
                    "stage_fallback_used": True,
                    "entry_only": entry_only,
                }

            lexical_hits_no_stage = await self._lexical_search_nodes(
                query=q,
                limit=limit,
                stage=None,
                service_id=service_id,
                entry_only=entry_only,
            )
            if lexical_hits_no_stage:
                return lexical_hits_no_stage, {
                    "search_mode": "lexical_stage_fallback",
                    "stage_fallback_used": True,
                    "entry_only": entry_only,
                }

        return [], {
            "search_mode": "no_matches",
            "stage_fallback_used": bool(stage),
            "entry_only": entry_only,
        }

    async def _vector_search_nodes(
        self,
        *,
        query: str,
        limit: int,
        stage: str | None,
        service_id: str | None,
        entry_only: bool,
    ) -> list[ScriptFlowNodeHit]:
        if not self.openai_api_key:
            return []

        query_embedding = await create_embedding(
            query,
            openai_api_key=self.openai_api_key,
            db=self.db,
            tenant_id=self.tenant_id,
            charge_source_type="embedding.script_flow_query",
            charge_metadata={"agent_id": str(self.agent_id)},
        )
        if query_embedding is None:
            return []

        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        where_sql = [
            "tenant_id = :tenant_id",
            "agent_id = :agent_id",
            "is_searchable = true",
            "embedding IS NOT NULL",
        ]
        params: dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "embedding": embedding_str,
            "limit": max(1, limit),
        }
        if stage:
            where_sql.append("stage = :stage")
            params["stage"] = stage
        if service_id:
            where_sql.append("service_ids @> :service_ids::jsonb")
            params["service_ids"] = f'["{service_id}"]'
        if entry_only:
            where_sql.append("node_type = 'trigger'")

        sql = text(
            f"""
            SELECT
                flow_id,
                node_id,
                node_type,
                title,
                stage,
                content_text,
                service_ids,
                employee_ids,
                motive_ids,
                objection_ids,
                proof_ids,
                constraint_ids,
                required_followup_question,
                communication_style,
                preferred_phrases,
                forbidden_phrases,
                1 - (embedding <=> CAST(:embedding AS vector)) AS score
            FROM script_flow_node_indexes
            WHERE {' AND '.join(where_sql)}
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        )
        rows = (await self.db.execute(sql, params)).fetchall()
        return [self._hit_from_row(row, score=float(row.score or 0.0)) for row in rows]

    async def _lexical_search_nodes(
        self,
        *,
        query: str,
        limit: int,
        stage: str | None,
        service_id: str | None,
        entry_only: bool,
    ) -> list[ScriptFlowNodeHit]:
        q = query.strip()
        q_lower = q.lower()
        like = f"%{q}%"
        tokens = self._lexical_tokens(q)

        score_expr = (
            case((func.lower(ScriptFlowNodeIndex.title) == q_lower, 1.0), else_=0.0)
            + case((ScriptFlowNodeIndex.title.ilike(like), 0.7), else_=0.0)
            + case((ScriptFlowNodeIndex.content_text.ilike(like), 0.45), else_=0.0)
        )

        token_filters = []
        for token in tokens:
            token_like = f"%{token}%"
            token_filters.append(ScriptFlowNodeIndex.title.ilike(token_like))
            token_filters.append(ScriptFlowNodeIndex.content_text.ilike(token_like))
            score_expr = score_expr + case(
                (ScriptFlowNodeIndex.title.ilike(token_like), literal(0.22)),
                else_=literal(0.0),
            )
            score_expr = score_expr + case(
                (ScriptFlowNodeIndex.content_text.ilike(token_like), literal(0.12)),
                else_=literal(0.0),
            )

        score_expr = score_expr.label("score")

        filters = [
            ScriptFlowNodeIndex.tenant_id == self.tenant_id,
            ScriptFlowNodeIndex.agent_id == self.agent_id,
            ScriptFlowNodeIndex.is_searchable.is_(True),
            or_(
                ScriptFlowNodeIndex.title.ilike(like),
                ScriptFlowNodeIndex.content_text.ilike(like),
                *token_filters,
            ),
        ]
        if stage:
            filters.append(ScriptFlowNodeIndex.stage == stage)
        if service_id:
            filters.append(ScriptFlowNodeIndex.service_ids.contains([service_id]))
        if entry_only:
            filters.append(ScriptFlowNodeIndex.node_type == "trigger")

        stmt = (
            select(ScriptFlowNodeIndex, score_expr)
            .where(and_(*filters))
            .order_by(score_expr.desc(), ScriptFlowNodeIndex.updated_at.desc())
            .limit(max(1, limit))
        )
        rows = (await self.db.execute(stmt)).all()

        return [self._hit_from_model(row, score=float(score or 0.0)) for row, score in rows]

    @staticmethod
    def _lexical_tokens(query: str) -> list[str]:
        raw_tokens = re.findall(r"[\wа-яА-ЯёЁ]{3,}", query.lower())
        stop_words = {
            "что", "это", "как", "для", "или", "есть", "мне", "вам", "нас",
            "вас", "про", "под", "над", "при", "без", "ли", "где", "когда",
            "какая", "какой", "какие", "какую", "можно", "нужно", "очень", "просто",
            "добрый", "день", "здравствуйте", "привет",
        }
        seen: set[str] = set()
        tokens: list[str] = []
        for token in raw_tokens:
            if token in stop_words:
                continue
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)
        return tokens[:8]

    def _hit_from_model(self, row: ScriptFlowNodeIndex, *, score: float) -> ScriptFlowNodeHit:
        return ScriptFlowNodeHit(
            flow_id=row.flow_id,
            node_id=row.node_id,
            node_type=row.node_type,
            title=row.title,
            score=score,
            stage=row.stage,
            content_text=row.content_text,
            metadata={
                "service_ids": list(row.service_ids or []),
                "employee_ids": list(row.employee_ids or []),
                "motive_ids": list(row.motive_ids or []),
                "objection_ids": list(row.objection_ids or []),
                "proof_ids": list(row.proof_ids or []),
                "constraint_ids": list(row.constraint_ids or []),
                "required_followup_question": row.required_followup_question,
                "communication_style": row.communication_style,
                "preferred_phrases": list(row.preferred_phrases or []),
                "forbidden_phrases": list(row.forbidden_phrases or []),
            },
        )

    def _hit_from_row(self, row: Any, *, score: float) -> ScriptFlowNodeHit:
        return ScriptFlowNodeHit(
            flow_id=row.flow_id,
            node_id=row.node_id,
            node_type=row.node_type,
            title=row.title,
            score=score,
            stage=row.stage,
            content_text=row.content_text,
            metadata={
                "service_ids": list(row.service_ids or []),
                "employee_ids": list(row.employee_ids or []),
                "motive_ids": list(row.motive_ids or []),
                "objection_ids": list(row.objection_ids or []),
                "proof_ids": list(row.proof_ids or []),
                "constraint_ids": list(row.constraint_ids or []),
                "required_followup_question": row.required_followup_question,
                "communication_style": row.communication_style,
                "preferred_phrases": list(row.preferred_phrases or []),
                "forbidden_phrases": list(row.forbidden_phrases or []),
            },
        )

    async def expand_neighborhood(
        self,
        hits: list[ScriptFlowNodeHit],
    ) -> list[dict[str, Any]]:
        """Expand top hits with 1-hop edges and neighbor node titles."""
        if not hits:
            return []

        hit_node_ids = {h.node_id for h in hits}
        hit_flow_ids = {h.flow_id for h in hits}

        edges_stmt = select(ScriptFlowEdgeIndex).where(
            ScriptFlowEdgeIndex.tenant_id == self.tenant_id,
            ScriptFlowEdgeIndex.agent_id == self.agent_id,
            ScriptFlowEdgeIndex.flow_id.in_(hit_flow_ids),
            or_(
                ScriptFlowEdgeIndex.source_node_id.in_(hit_node_ids),
                ScriptFlowEdgeIndex.target_node_id.in_(hit_node_ids),
            ),
        )
        edges = (await self.db.execute(edges_stmt)).scalars().all()

        neighbor_ids: set[str] = set()
        for e in edges:
            neighbor_ids.add(e.source_node_id)
            neighbor_ids.add(e.target_node_id)

        neighbor_title_map: dict[tuple[UUID, str], str] = {}
        if neighbor_ids:
            nodes_stmt = select(
                ScriptFlowNodeIndex.flow_id,
                ScriptFlowNodeIndex.node_id,
                ScriptFlowNodeIndex.title,
            ).where(
                ScriptFlowNodeIndex.tenant_id == self.tenant_id,
                ScriptFlowNodeIndex.agent_id == self.agent_id,
                ScriptFlowNodeIndex.flow_id.in_(hit_flow_ids),
                ScriptFlowNodeIndex.node_id.in_(neighbor_ids),
            )
            for flow_id, node_id, title in (await self.db.execute(nodes_stmt)).all():
                neighbor_title_map[(flow_id, node_id)] = title

        docs: list[dict[str, Any]] = []
        for hit in hits:
            linked_edges = [
                e
                for e in edges
                if e.flow_id == hit.flow_id
                and (e.source_node_id == hit.node_id or e.target_node_id == hit.node_id)
            ]
            docs.append(
                {
                    "flow_id": str(hit.flow_id),
                    "node_id": hit.node_id,
                    "node_type": hit.node_type,
                    "title": hit.title,
                    "score": hit.score,
                    "stage": hit.stage,
                    "content_text": hit.content_text,
                    "metadata": hit.metadata,
                    "neighbors": [
                        {
                            "source_node_id": e.source_node_id,
                            "target_node_id": e.target_node_id,
                            "source_title": neighbor_title_map.get((hit.flow_id, e.source_node_id)),
                            "target_title": neighbor_title_map.get((hit.flow_id, e.target_node_id)),
                            "branch_label": e.branch_label,
                        }
                        for e in linked_edges
                    ],
                }
            )
        return docs

    async def build_context_packet(
        self,
        *,
        query: str,
        stage: str | None = None,
        service_id: str | None = None,
        entry_only: bool = False,
    ) -> ScriptFlowContextPacket:
        """Build the future runtime packet for scenario answering."""
        hits, search_debug = await self.search_nodes_with_debug(
            query=query,
            stage=stage,
            service_id=service_id,
            entry_only=entry_only,
        )
        neighborhoods = await self.expand_neighborhood(hits)
        return ScriptFlowContextPacket(
            query=query,
            matches=neighborhoods,
            debug={
                "stage": stage,
                "service_id": service_id,
                "entry_only": entry_only,
                "semantic_hit_count": len(hits),
                "engine": "pgvector_or_lexical_fallback",
                **search_debug,
            },
        )
