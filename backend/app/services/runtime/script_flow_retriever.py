"""Lightweight retrieval interface for pgvector-based script flow search."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any
from uuid import UUID

from sqlalchemy import and_, bindparam, case, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.script_flow_edge_index import ScriptFlowEdgeIndex
from app.db.models.script_flow_node_index import ScriptFlowNodeIndex
from app.services.directory.service import create_embedding

# Hybrid RRF: слияние векторного и лексического пулов.
_RRF_K = 60          # сглаживающая константа Reciprocal Rank Fusion
_HYBRID_POOL = 20    # размер каждого пула до слияния
_LEXICAL_MIN = 0.4   # порог лексического скора для «спасения» узла, недобранного вектором
                     # (content ILIKE = 0.45 → подстрочное совпадение проходит)


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
        min_score: float = 0.0,
        flow_ids: list[UUID] | None = None,
    ) -> list[ScriptFlowNodeHit]:
        hits, _debug = await self.search_nodes_with_debug(
            query=query,
            limit=limit,
            stage=stage,
            service_id=service_id,
            entry_only=entry_only,
            min_score=min_score,
            flow_ids=flow_ids,
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
        min_score: float = 0.0,
        flow_ids: list[UUID] | None = None,
    ) -> tuple[list[ScriptFlowNodeHit], dict[str, Any]]:
        """Return node matches via pgvector with lexical fallback.

        Semantics:
        - Если у нод есть эмбеддинги (vector-путь вернул строки) — работаем строго
          семантически и применяем порог `min_score`. Если ничего не прошло порог —
          возвращаем пусто (тактику не подставляем → агент отвечает по основному
          промпту). Лексику в этом случае НЕ включаем, чтобы не подсунуть мусор.
        - Если эмбеддингов нет вовсе (переходный период / сбой API) — лексический
          фолбэк по ILIKE.
        Stage — мягкий фильтр: при пустом результате пробуем без stage.
        """
        q = (query or "").strip()
        if not q:
            return [], {
                "search_mode": "empty_query",
                "stage_fallback_used": False,
                "entry_only": entry_only,
            }

        pool = max(limit, _HYBRID_POOL)

        async def _hybrid(stage_arg: str | None) -> tuple[list[ScriptFlowNodeHit] | None, list[ScriptFlowNodeHit]]:
            """Возврат (vector_hits|None, fused). None у vector_hits — эмбеддингов нет вовсе."""
            vhits = await self._vector_search_nodes(
                query=q, limit=pool, stage=stage_arg, service_id=service_id,
                entry_only=entry_only, flow_ids=flow_ids,
            )
            if not vhits:
                return None, []
            lhits = await self._lexical_search_nodes(
                query=q, limit=pool, stage=stage_arg, service_id=service_id,
                entry_only=entry_only, flow_ids=flow_ids,
            )
            return vhits, self._rrf_fuse(vhits, lhits, min_score=min_score, limit=limit)

        vector_hits, fused = await _hybrid(stage)

        if vector_hits is None:
            # Эмбеддингов нет вовсе → чистый лексический фолбэк.
            lexical_hits = await self._lexical_search_nodes(
                query=q, limit=limit, stage=stage, service_id=service_id,
                entry_only=entry_only, flow_ids=flow_ids,
            )
            if lexical_hits:
                return lexical_hits, {
                    "search_mode": "lexical_stage_filtered" if stage else "lexical",
                    "stage_fallback_used": False,
                    "entry_only": entry_only,
                }
            if stage:
                lexical_hits_no_stage = await self._lexical_search_nodes(
                    query=q, limit=limit, stage=None, service_id=service_id,
                    entry_only=entry_only, flow_ids=flow_ids,
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

        if fused:
            return fused, {
                "search_mode": "hybrid_stage_filtered" if stage else "hybrid",
                "stage_fallback_used": False,
                "entry_only": entry_only,
                "min_score": min_score,
            }

        if stage:
            _v2, fused_no_stage = await _hybrid(None)
            if fused_no_stage:
                return fused_no_stage, {
                    "search_mode": "hybrid_stage_fallback",
                    "stage_fallback_used": True,
                    "entry_only": entry_only,
                    "min_score": min_score,
                }

        # Эмбеддинги есть, но ни вектор, ни лексика не прошли гейт → нет тактики → базовый промпт.
        return [], {
            "search_mode": "hybrid_below_threshold",
            "stage_fallback_used": bool(stage),
            "entry_only": entry_only,
            "min_score": min_score,
            "top_score": max((h.score for h in vector_hits), default=0.0),
        }

    @staticmethod
    def _rrf_fuse(
        vector_hits: list[ScriptFlowNodeHit],
        lexical_hits: list[ScriptFlowNodeHit],
        *,
        min_score: float,
        limit: int,
        k: int = _RRF_K,
        lexical_min: float = _LEXICAL_MIN,
    ) -> list[ScriptFlowNodeHit]:
        """Слить векторный и лексический пулы через RRF.

        Ранжирование — по Σ 1/(k+rank). Гейт уверенности (сохраняет фолбэк на
        базовый промпт): узел проходит, если у него сильный вектор (cosine ≥
        min_score) ИЛИ сильная лексика (score ≥ lexical_min). При min_score ≤ 0
        (sandbox) гейт отключён. Отображаемый score — cosine, если есть, иначе
        лексический.
        """
        def _key(h: ScriptFlowNodeHit) -> tuple[UUID, str]:
            return (h.flow_id, h.node_id)

        v_score = {_key(h): h.score for h in vector_hits}
        l_score = {_key(h): h.score for h in lexical_hits}
        v_rank = {_key(h): i for i, h in enumerate(vector_hits)}
        l_rank = {_key(h): i for i, h in enumerate(lexical_hits)}

        hit_by_key: dict[tuple[UUID, str], ScriptFlowNodeHit] = {}
        for h in vector_hits:
            hit_by_key.setdefault(_key(h), h)
        for h in lexical_hits:
            hit_by_key.setdefault(_key(h), h)

        scored: list[tuple[float, float, ScriptFlowNodeHit]] = []
        for kk, hit in hit_by_key.items():
            vs = v_score.get(kk)
            ls = l_score.get(kk)
            passes = (
                min_score <= 0.0
                or (vs is not None and vs >= min_score)
                or (ls is not None and ls >= lexical_min)
            )
            if not passes:
                continue
            rrf = 0.0
            if kk in v_rank:
                rrf += 1.0 / (k + v_rank[kk])
            if kk in l_rank:
                rrf += 1.0 / (k + l_rank[kk])
            display = vs if vs is not None else (ls if ls is not None else 0.0)
            scored.append((rrf, float(display), hit))

        scored.sort(key=lambda t: t[0], reverse=True)
        out: list[ScriptFlowNodeHit] = []
        for _rrf, display, hit in scored[: max(1, limit)]:
            hit.score = display
            out.append(hit)
        return out

    async def _vector_search_nodes(
        self,
        *,
        query: str,
        limit: int,
        stage: str | None,
        service_id: str | None,
        entry_only: bool,
        flow_ids: list[UUID] | None = None,
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

        # Pass as TEXT literal so asyncpg doesn't try to encode it as a vector client-side.
        embedding_str = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"
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
        if flow_ids:
            where_sql.append("flow_id IN :flow_ids")
            params["flow_ids"] = list(flow_ids)

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
                1 - (embedding <=> CAST(CAST(:embedding AS text) AS vector)) AS score
            FROM script_flow_node_indexes
            WHERE {' AND '.join(where_sql)}
            ORDER BY embedding <=> CAST(CAST(:embedding AS text) AS vector)
            LIMIT :limit
            """
        )
        if flow_ids:
            sql = sql.bindparams(bindparam("flow_ids", expanding=True))
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
        flow_ids: list[UUID] | None = None,
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
        if flow_ids:
            filters.append(ScriptFlowNodeIndex.flow_id.in_(flow_ids))

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
        min_score: float = 0.0,
        flow_ids: list[UUID] | None = None,
    ) -> ScriptFlowContextPacket:
        """Build the future runtime packet for scenario answering."""
        hits, search_debug = await self.search_nodes_with_debug(
            query=query,
            stage=stage,
            service_id=service_id,
            entry_only=entry_only,
            min_score=min_score,
            flow_ids=flow_ids,
        )
        neighborhoods = await self.expand_neighborhood(hits)
        return ScriptFlowContextPacket(
            query=query,
            matches=neighborhoods,
            debug={
                "stage": stage,
                "service_id": service_id,
                "entry_only": entry_only,
                "min_score": min_score,
                "semantic_hit_count": len(hits),
                "engine": "pgvector_or_lexical_fallback",
                **search_debug,
            },
        )
