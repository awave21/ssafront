"""Hybrid graph retrieval поверх Neo4j.

Поиск гибридный: vector index `node_searchable_embedding` + fulltext index `node_text`,
объединение через Reciprocal Rank Fusion (RRF). После RRF — graph augmentation
тем же путём, что раньше: подтягиваются соседи через рёбра HAS_SEMANTIC,
COVERS_SERVICE, PROVIDED_BY, GRAPH_RELATION.

Embedding запроса считается в Python (через текущий create_embedding) и
передаётся в Cypher параметром, потому что в Neo4j нет GenAI plugin
(`vector.encode.openai` недоступна).
"""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import structlog
from neo4j import Driver

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_RRF_K = 60


class GraphRetrievalResult:
    """Retrieval result with graph context: service + objections + tactics + specialists."""

    def __init__(
        self,
        title: str,
        node_label: str,
        situation: str | None = None,
        approach: str | None = None,
        phrases: str | None = None,
        service_name: str | None = None,
        service_external_id: int | None = None,
        objections: list[str] | None = None,
        tactics: list[str] | None = None,
        specialists: list[dict[str, Any]] | None = None,
        score: float = 0.0,
        content_text: str = "",
        service_description: str = "",
        specialist_info: str = "",
    ) -> None:
        self.title = title
        self.node_label = node_label
        self.situation = situation
        self.approach = approach
        self.phrases = phrases
        self.service_name = service_name
        self.service_external_id = service_external_id
        self.objections = objections or []
        self.tactics = tactics or []
        self.specialists = specialists or []
        self.score = score
        self.content_text = content_text or ""
        self.service_description = service_description or ""
        self.specialist_info = specialist_info or ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "node_label": self.node_label,
            "situation": self.situation,
            "approach": self.approach,
            "phrases": self.phrases,
            "content_text": self.content_text,
            "service_name": self.service_name,
            "service_external_id": self.service_external_id,
            "service_description": self.service_description,
            "specialist_info": self.specialist_info,
            "objections": self.objections,
            "tactics": self.tactics,
            "specialists": self.specialists,
            "score": round(self.score, 4),
        }


class HybridGraphRetriever:
    """Hybrid retriever: vector + fulltext via RRF, plus graph augmentation."""

    _VECTOR_QUERY = """
    CALL db.index.vector.queryNodes('node_searchable_embedding', $top_k, $query_vector)
    YIELD node, score
    WHERE node.tenant_id = $tenant_id AND node.agent_id = $agent_id
    RETURN elementId(node) AS eid, score
    ORDER BY score DESC
    """

    _FULLTEXT_QUERY = """
    CALL db.index.fulltext.queryNodes('node_text', $query_text)
    YIELD node, score
    WHERE node.tenant_id = $tenant_id AND node.agent_id = $agent_id
      AND 'Searchable' IN labels(node)
    RETURN elementId(node) AS eid, score
    ORDER BY score DESC
    """

    _AUGMENTATION_QUERY = """
    UNWIND $candidates AS c
    MATCH (node) WHERE elementId(node) = c.eid
    WITH node, c.score AS score, head(labels(node)) AS node_label

    // 1) :FlowNode → услуги и специалисты по списочным свойствам
    OPTIONAL MATCH (svc_via_flow:Service)
      WHERE node_label = 'FlowNode'
        AND node.service_ids IS NOT NULL
        AND toString(svc_via_flow.external_id) IN node.service_ids
        AND svc_via_flow.agent_id = node.agent_id
    OPTIONAL MATCH (sp_via_flow:Specialist)
      WHERE node_label = 'FlowNode'
        AND node.employee_ids IS NOT NULL
        AND toString(sp_via_flow.external_id) IN node.employee_ids
        AND sp_via_flow.agent_id = node.agent_id

    // 2) :GraphNode → канвас-нода через :HAS_SEMANTIC
    OPTIONAL MATCH (canvas_for_graph:FlowNode)-[:HAS_SEMANTIC]->(node)
      WHERE node_label = 'GraphNode'

    // 3) :Service → специалисты + канвас-ноды
    OPTIONAL MATCH (node)-[:PROVIDED_BY]->(sp_self_svc:Specialist)
      WHERE node_label = 'Service'
    OPTIONAL MATCH (canvas_for_svc:FlowNode)
      WHERE node_label = 'Service'
        AND canvas_for_svc.service_ids IS NOT NULL
        AND toString(node.external_id) IN canvas_for_svc.service_ids
        AND canvas_for_svc.agent_id = node.agent_id

    // 4) :Specialist → услуги + канвас-ноды
    OPTIONAL MATCH (svc_back:Service)-[:PROVIDED_BY]->(node)
      WHERE node_label = 'Specialist'
    OPTIONAL MATCH (canvas_for_sp:FlowNode)
      WHERE node_label = 'Specialist'
        AND canvas_for_sp.employee_ids IS NOT NULL
        AND toString(node.external_id) IN canvas_for_sp.employee_ids
        AND canvas_for_sp.agent_id = node.agent_id

    WITH node, score, node_label,
         CASE node_label
              WHEN 'FlowNode' THEN node
              ELSE coalesce(canvas_for_graph, canvas_for_svc, canvas_for_sp)
         END AS canvas_anchor,
         coalesce(svc_via_flow, svc_back) AS service_anchor,
         [x IN [sp_via_flow, sp_self_svc] WHERE x IS NOT NULL | x] AS specialists_collected

    OPTIONAL MATCH (canvas_anchor)-[:HAS_SEMANTIC]->(obj:GraphNode)
      WHERE obj.entity_type IN ['objection', 'concern']
    OPTIONAL MATCH (canvas_anchor)-[:HAS_SEMANTIC]->(tac:GraphNode)
      WHERE tac.entity_type = 'tactic'

    RETURN
      coalesce(node.title, node.name) AS title,
      node_label,
      coalesce(canvas_anchor.situation, node.situation) AS situation,
      coalesce(canvas_anchor.approach, node.approach) AS approach,
      coalesce(canvas_anchor.example_phrases, node.example_phrases) AS phrases,
      coalesce(service_anchor.name,
               CASE WHEN node_label = 'Service' THEN node.name ELSE NULL END) AS service_name,
      coalesce(service_anchor.external_id,
               CASE WHEN node_label = 'Service' THEN node.external_id ELSE NULL END) AS service_external_id,
      collect(DISTINCT obj.title) AS objections,
      collect(DISTINCT tac.title) AS tactics,
      [sp IN specialists_collected | sp {.name, .external_id}] +
        CASE WHEN node_label = 'Specialist'
             THEN [{name: node.name, external_id: node.external_id}]
             ELSE [] END AS specialists,
      score,
      coalesce(canvas_anchor.content_text, node.description, node.content_text, '') AS content_text,
      coalesce(service_anchor.description,
               CASE WHEN node_label = 'Service' THEN node.description ELSE NULL END, '') AS service_description,
      CASE WHEN node_label = 'Specialist' THEN coalesce(node.information, '') ELSE '' END AS specialist_info
    ORDER BY score DESC
    """

    def __init__(
        self,
        driver: Driver,
        agent_id: UUID,
        tenant_id: UUID,
    ) -> None:
        self.driver = driver
        self.agent_id = str(agent_id)
        self.tenant_id = str(tenant_id)
        self._min_score = float(get_settings().unified_graph_retriever_min_score)

    async def search(
        self,
        query_text: str,
        top_k: int = 10,
        openai_api_key: str | None = None,
    ) -> list[GraphRetrievalResult]:
        """Hybrid search: vector + fulltext via RRF, then graph augmentation.

        Steps:
        1. Compute query embedding (via OpenAI in Python)
        2. Run vector search (top_k * 3 candidates)
        3. Run fulltext search (top_k * 3 candidates)
        4. RRF merge: rrf = Σ 1 / (RRF_K + rank)
        5. Take top top_k * 5 candidates, run augmentation Cypher
        6. Filter by relative similarity threshold
        """
        if not openai_api_key:
            logger.warning("graph_retriever_no_api_key", agent_id=self.agent_id)
            return []

        from app.services.directory.service import create_embedding

        query_embedding = await create_embedding(
            query_text,
            openai_api_key=openai_api_key,
            charge_source_type="embedding.graph_retriever_query",
            charge_metadata={"agent_id": self.agent_id},
        )
        if not query_embedding:
            logger.warning("graph_retriever_embedding_failed", agent_id=self.agent_id)
            return []

        candidate_pool = max(int(top_k) * 3, 30)
        merge_pool = max(int(top_k) * 5, 50)
        fts_query_text = _build_fts_query(query_text)

        rrf_scores: dict[str, float] = {}
        vec_count = 0
        fts_count = 0

        try:
            with self.driver.session() as session:
                vec_rows = session.run(
                    self._VECTOR_QUERY,
                    query_vector=query_embedding,
                    tenant_id=self.tenant_id,
                    agent_id=self.agent_id,
                    top_k=candidate_pool,
                )
                for rank, row in enumerate(vec_rows):
                    eid = row["eid"]
                    if not eid:
                        continue
                    rrf_scores[eid] = rrf_scores.get(eid, 0.0) + 1.0 / (_RRF_K + rank)
                    vec_count += 1

                if fts_query_text:
                    fts_rows = session.run(
                        self._FULLTEXT_QUERY,
                        query_text=fts_query_text,
                        tenant_id=self.tenant_id,
                        agent_id=self.agent_id,
                    )
                    for rank, row in enumerate(fts_rows):
                        eid = row["eid"]
                        if not eid:
                            continue
                        rrf_scores[eid] = rrf_scores.get(eid, 0.0) + 1.0 / (_RRF_K + rank)
                        fts_count += 1
                        if fts_count >= candidate_pool:
                            break

                if not rrf_scores:
                    return []

                top_candidates = sorted(rrf_scores.items(), key=lambda x: -x[1])[:merge_pool]
                candidates_param = [{"eid": eid, "score": score} for eid, score in top_candidates]

                aug_rows = session.run(
                    self._AUGMENTATION_QUERY,
                    candidates=candidates_param,
                )

                results: list[GraphRetrievalResult] = []
                seen: set[tuple[str, str, float]] = set()
                for row in aug_rows:
                    result = self._parse_row(row)
                    if not result:
                        continue
                    key = (result.title, result.node_label, round(result.score, 4))
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(result)
                    if len(results) >= int(top_k):
                        break
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "graph_retriever_search_failed",
                agent_id=self.agent_id,
                query_text=query_text[:100],
                error=str(exc),
            )
            return []

        results = self._apply_min_score_filter(results)

        logger.info(
            "graph_retriever_hybrid_search",
            agent_id=self.agent_id,
            query=query_text[:100],
            vec_count=vec_count,
            fts_count=fts_count,
            merged_count=len(rrf_scores),
            returned=len(results),
        )
        return results

    def _apply_min_score_filter(
        self, results: list[GraphRetrievalResult]
    ) -> list[GraphRetrievalResult]:
        if not results or self._min_score <= 0:
            return results
        max_s = max(r.score for r in results)
        if max_s <= 0:
            return results
        return [r for r in results if r.score / max_s >= self._min_score]

    def _parse_row(self, row: Any) -> GraphRetrievalResult | None:
        try:
            title = row.get("title") or ""
            node_label = row.get("node_label") or "unknown"

            specialists_raw = row.get("specialists") or []
            specialists: list[dict[str, Any]] = []
            seen_ids: set[Any] = set()
            for sp in specialists_raw:
                if isinstance(sp, dict):
                    ext_id = sp.get("external_id")
                    if ext_id is not None and ext_id not in seen_ids:
                        specialists.append({"name": sp.get("name", ""), "external_id": ext_id})
                        seen_ids.add(ext_id)

            return GraphRetrievalResult(
                title=title,
                node_label=node_label,
                situation=row.get("situation"),
                approach=row.get("approach"),
                phrases=row.get("phrases"),
                service_name=row.get("service_name"),
                service_external_id=row.get("service_external_id"),
                objections=[str(o).strip() for o in (row.get("objections") or []) if o],
                tactics=[str(t).strip() for t in (row.get("tactics") or []) if t],
                specialists=specialists,
                score=float(row.get("score") or 0.0),
                content_text=str(row.get("content_text") or ""),
                service_description=str(row.get("service_description") or ""),
                specialist_info=str(row.get("specialist_info") or ""),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph_retrieval_parse_failed", error=str(exc))
            return None


_FTS_SPECIAL_CHARS = re.compile(r'[+\-!(){}\[\]\^"~*?:\\/&|]')


def _build_fts_query(query_text: str) -> str:
    """Подготовить query для Lucene fulltext index.

    - Эскейпит спецсимволы Lucene
    - Каждый токен делает префиксным (`token*`) для toleration коротких/неполных слов
    - Соединяет через OR — любое совпадение подходит, ranking сделает RRF
    """
    if not query_text:
        return ""
    cleaned = _FTS_SPECIAL_CHARS.sub(" ", query_text).strip()
    if not cleaned:
        return ""
    tokens = [t for t in cleaned.split() if len(t) >= 2]
    if not tokens:
        return ""
    return " OR ".join(f"{t}*" for t in tokens[:12])


def get_hybrid_graph_retriever(
    agent_id: UUID,
    tenant_id: UUID,
) -> HybridGraphRetriever:
    """Factory to get configured HybridGraphRetriever for an agent."""
    from app.services.runtime.neo4j_client import get_neo4j_driver

    driver = get_neo4j_driver()
    if driver is None:
        raise RuntimeError("Neo4j driver not available")

    return HybridGraphRetriever(
        driver=driver,
        agent_id=agent_id,
        tenant_id=tenant_id,
    )
