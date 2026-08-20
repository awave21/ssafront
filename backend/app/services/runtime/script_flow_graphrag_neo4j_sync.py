from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.script_flow import ScriptFlow
from app.db.models.sqns_service import SqnsResource, SqnsService
from app.services.directory.service import create_embeddings_batch
from app.services.runtime.graphrag_tool import (
    _normalize_lookup_text,
    _score_candidate,
    _strip_service_code,
)
from app.services.runtime.neo4j_client import get_neo4j_driver
from app.services.script_flow_graphrag_compiler import ScriptFlowGraphRAGPayload

logger = structlog.get_logger(__name__)

_GRAPH_NODE_VECTOR_INDEX_NAME = "graph_node_embedding"
_VECTOR_DIMS = 1536


def _ensure_graph_node_vector_index(tx: Any) -> None:
    tx.run(
        f"""
        CREATE VECTOR INDEX {_GRAPH_NODE_VECTOR_INDEX_NAME} IF NOT EXISTS
        FOR (n:GraphNode) ON (n.embedding)
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {_VECTOR_DIMS},
            `vector.similarity_function`: 'cosine'
        }}}}
        """
    )


async def sync_script_flow_graphrag_to_neo4j(
    *,
    flow: ScriptFlow,
    payload: ScriptFlowGraphRAGPayload,
    db: AsyncSession,
    openai_api_key: str | None,
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

    # Skip canvas-kind GraphNodes — они дублируют :FlowNode (см. этап 9).
    # Relations с source/target начинающимся на "canvas:" перенаправляем на :FlowNode.
    persistable_nodes = [n for n in payload.nodes if str(n.node_kind) != "canvas"]

    # Compute embeddings in a single batched OpenAI request before Neo4j tx.
    # Включаем entity_type и stage_hint (из properties) — обогащает семантику для embedding.
    def _build_embedding_text(n: Any) -> str:
        props = n.properties if isinstance(n.properties, dict) else {}
        stage_hint = str(props.get("stage_hint") or "").strip()
        return " ".join(
            p
            for p in [
                (n.title or "").strip(),
                (n.entity_type or "").strip(),
                stage_hint,
                (n.description or "").strip(),
            ]
            if p
        )

    embedding_texts = [_build_embedding_text(n) for n in persistable_nodes]
    embeddings: list[list[float] | None] = []
    if persistable_nodes and openai_api_key:
        embeddings = await create_embeddings_batch(
            embedding_texts,
            openai_api_key=openai_api_key,
            db=db,
            tenant_id=flow.tenant_id,
            charge_source_type="embedding.script_flow_graphrag",
            charge_source_id=str(flow.id),
            charge_metadata={"agent_id": agent_id, "flow_id": flow_id},
        )
    else:
        embeddings = [None] * len(persistable_nodes)

    node_rows: list[dict[str, Any]] = []
    for idx, n in enumerate(persistable_nodes):
        node_rows.append({
            "graph_node_id": n.graph_node_id,
            "node_kind": str(n.node_kind),
            "entity_type": n.entity_type,
            "title": n.title,
            "description": n.description,
            "source_node_ids": n.source_node_ids or [],
            # Neo4j не принимает Map в property — сериализуем как JSON-строку
            "properties": json.dumps(n.properties or {}, ensure_ascii=False),
            "community_key": n.community_key,
            "embedding": embeddings[idx] if idx < len(embeddings) else None,
        })

    def _split_canvas_id(gid: str) -> tuple[bool, str]:
        """('canvas:n1') -> (True, 'n1'). ('library:service:1') -> (False, 'library:service:1')."""
        if isinstance(gid, str) and gid.startswith("canvas:"):
            return True, gid[len("canvas:"):]
        return False, gid

    # Делим relations на 4 группы по тому, является ли source/target canvas-prefix.
    # Каждая группа пишется своим Cypher-запросом с правильным MATCH.
    rels_gg: list[dict[str, Any]] = []  # graph -> graph
    rels_fg: list[dict[str, Any]] = []  # flow -> graph
    rels_gf: list[dict[str, Any]] = []  # graph -> flow
    rels_ff: list[dict[str, Any]] = []  # flow -> flow
    for r in payload.relations:
        s_is_canvas, s_id = _split_canvas_id(r.source_graph_node_id)
        t_is_canvas, t_id = _split_canvas_id(r.target_graph_node_id)
        row = {
            "source_id": s_id,
            "target_id": t_id,
            "source_orig": r.source_graph_node_id,
            "target_orig": r.target_graph_node_id,
            "relation_type": r.relation_type,
            "weight": r.weight,
            "properties": json.dumps(r.properties or {}, ensure_ascii=False),
        }
        if s_is_canvas and t_is_canvas:
            rels_ff.append(row)
        elif s_is_canvas:
            rels_fg.append(row)
        elif t_is_canvas:
            rels_gf.append(row)
        else:
            rels_gg.append(row)
    community_rows: list[dict[str, Any]] = [
        {
            "community_key": c.community_key,
            "title": c.title,
            "summary": c.summary,
            "node_ids": c.node_ids or [],
            "properties": json.dumps(c.properties or {}, ensure_ascii=False),
        }
        for c in payload.communities
    ]
    # ============================================================
    # Fuzzy-match: LLM-extracted services/specialists → real SQNS entities.
    # Для каждой entity с entity_type='service' ищем :Service в SQNS по name.
    # Если score >= 0.7 — пишем прямое ребро :FlowNode -[:COVERS_SERVICE]-> :Service.
    # Аналогично для specialist (threshold 0.85, ФИО строже).
    # ============================================================
    services_db = (
        await db.execute(
            select(SqnsService).where(
                and_(
                    SqnsService.agent_id == flow.agent_id,
                    SqnsService.is_enabled == True,  # noqa: E712
                    SqnsService.stale_since.is_(None),
                )
            )
        )
    ).scalars().all()
    specialists_db = (
        await db.execute(
            select(SqnsResource).where(
                and_(
                    SqnsResource.agent_id == flow.agent_id,
                    SqnsResource.is_active == True,  # noqa: E712
                    SqnsResource.active == True,  # noqa: E712
                )
            )
        )
    ).scalars().all()

    def _best_match(query_title: str, candidates: list[Any], get_name, threshold: float):
        """Возвращает (best_candidate, best_score) или (None, 0)."""
        q_norm = _normalize_lookup_text(_strip_service_code(query_title or ""))
        if not q_norm:
            return None, 0.0
        best, best_score = None, 0.0
        for cand in candidates:
            cand_name = _strip_service_code(get_name(cand) or "")
            score = _score_candidate(q_norm, cand_name)
            if score > best_score:
                best, best_score = cand, score
        if best_score >= threshold:
            return best, best_score
        return None, best_score

    # Собираем список (canvas_node_id, service.external_id) и (canvas_node_id, specialist.external_id)
    covers_service_pairs: list[tuple[str, int]] = []
    has_specialist_pairs: list[tuple[str, int]] = []
    matched_count = 0
    skipped_count = 0

    for n in payload.nodes:
        canvas_ids = [str(c) for c in (n.source_node_ids or []) if c]
        if not canvas_ids:
            continue
        if n.entity_type == "service":
            matched, score = _best_match(n.title, services_db, lambda s: s.name, 0.7)
            if matched is not None:
                matched_count += 1
                for cnid in canvas_ids:
                    covers_service_pairs.append((cnid, matched.external_id))
            else:
                skipped_count += 1
        elif n.entity_type == "specialist":
            matched, score = _best_match(n.title, specialists_db, lambda s: s.name, 0.85)
            if matched is not None:
                matched_count += 1
                for cnid in canvas_ids:
                    has_specialist_pairs.append((cnid, matched.external_id))
            else:
                skipped_count += 1

    logger.info(
        "fuzzy_match_summary",
        flow_id=flow_id,
        services_db=len(services_db),
        specialists_db=len(specialists_db),
        covers_service_pairs=len(covers_service_pairs),
        has_specialist_pairs=len(has_specialist_pairs),
        matched=matched_count,
        skipped=skipped_count,
        sample_pairs=[(c, e, type(e).__name__) for c, e in covers_service_pairs[:3]],
    )

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
            "debug": json.dumps(payload.diagnostic.debug or {}, ensure_ascii=False),
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
        # Расширенный семантический слой (communities/diagnostics/GRAPH_RELATION) — по флагу.
        # По умолчанию off: для тактик достаточно GraphNode + HAS_SEMANTIC. DETACH DELETE выше
        # чистит старое, а при _extended=False новое не создаётся → слой не возвращается.
        _extended = settings.script_flow_graphrag_extended
        for node in node_rows:
            tx.run(
                """
                MERGE (n:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, graph_node_id: $graph_node_id})
                SET n:Searchable,
                    n.flow_version = $flow_version,
                    n.node_kind = $node_kind,
                    n.entity_type = $entity_type,
                    n.title = $title,
                    n.description = $description,
                    n.content_text = $description,
                    n.source_node_ids = $source_node_ids,
                    n.properties = $properties,
                    n.community_key = $community_key,
                    n.embedding = $embedding
                """,
                tenant_id=tenant_id,
                agent_id=agent_id,
                flow_id=flow_id,
                flow_version=flow_version,
                **node,
            )

            # Create HAS_SEMANTIC edges from FlowNode to GraphNode
            # source_node_ids contains the canvas node_id(s) that produced this GraphNode
            for canvas_node_id in node["source_node_ids"]:
                tx.run(
                    """
                    MATCH (f:FlowNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, node_id: $canvas_node_id})
                    MATCH (g:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, graph_node_id: $graph_node_id})
                    MERGE (f)-[:HAS_SEMANTIC {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id}]->(g)
                    """,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    flow_id=flow_id,
                    canvas_node_id=canvas_node_id,
                    graph_node_id=node["graph_node_id"],
                )
        for community in (community_rows if _extended else []):
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
        # graph → graph (оба узла — :GraphNode)
        for rel in (rels_gg if _extended else []):
            tx.run(
                """
                MATCH (s:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, graph_node_id: $source_id})
                MATCH (t:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, graph_node_id: $target_id})
                MERGE (s)-[r:GRAPH_RELATION {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, relation_type: $relation_type, source_graph_node_id: $source_orig, target_graph_node_id: $target_orig}]->(t)
                SET r.weight = $weight, r.properties = $properties
                """,
                tenant_id=tenant_id, agent_id=agent_id, flow_id=flow_id, **rel,
            )
        # flow → graph (canvas: → :GraphNode) — самый частый кейс из LLM-extraction'а
        for rel in (rels_fg if _extended else []):
            tx.run(
                """
                MATCH (s:FlowNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, node_id: $source_id})
                MATCH (t:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, graph_node_id: $target_id})
                MERGE (s)-[r:GRAPH_RELATION {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, relation_type: $relation_type, source_graph_node_id: $source_orig, target_graph_node_id: $target_orig}]->(t)
                SET r.weight = $weight, r.properties = $properties
                """,
                tenant_id=tenant_id, agent_id=agent_id, flow_id=flow_id, **rel,
            )
        # graph → flow
        for rel in (rels_gf if _extended else []):
            tx.run(
                """
                MATCH (s:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, graph_node_id: $source_id})
                MATCH (t:FlowNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, node_id: $target_id})
                MERGE (s)-[r:GRAPH_RELATION {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, relation_type: $relation_type, source_graph_node_id: $source_orig, target_graph_node_id: $target_orig}]->(t)
                SET r.weight = $weight, r.properties = $properties
                """,
                tenant_id=tenant_id, agent_id=agent_id, flow_id=flow_id, **rel,
            )
        # flow → flow (редкий кейс: связь между двумя канвас-нодами через LLM)
        for rel in (rels_ff if _extended else []):
            tx.run(
                """
                MATCH (s:FlowNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, node_id: $source_id})
                MATCH (t:FlowNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, node_id: $target_id})
                MERGE (s)-[r:GRAPH_RELATION {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, relation_type: $relation_type, source_graph_node_id: $source_orig, target_graph_node_id: $target_orig}]->(t)
                SET r.weight = $weight, r.properties = $properties
                """,
                tenant_id=tenant_id, agent_id=agent_id, flow_id=flow_id, **rel,
            )

        # FlowNode -[:COVERS_SERVICE]-> :Service (fuzzy-match LLM-extracted services)
        cs_created = 0
        for canvas_node_id, svc_external_id in covers_service_pairs:
            res = tx.run(
                """
                MATCH (f:FlowNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, node_id: $canvas_node_id})
                MATCH (s:Service {tenant_id: $tenant_id, agent_id: $agent_id, external_id: $svc_external_id})
                MERGE (f)-[r:COVERS_SERVICE {tenant_id: $tenant_id, agent_id: $agent_id}]->(s)
                RETURN id(r) AS rid
                """,
                tenant_id=tenant_id,
                agent_id=agent_id,
                flow_id=flow_id,
                canvas_node_id=canvas_node_id,
                svc_external_id=svc_external_id,
            )
            rids = list(res)
            if rids:
                cs_created += 1
        logger.info("covers_service_attempts", flow_id=flow_id, attempted=len(covers_service_pairs), created=cs_created)

        # FlowNode -[:HAS_SPECIALIST]-> :Specialist (fuzzy-match LLM-extracted specialists)
        for canvas_node_id, sp_external_id in has_specialist_pairs:
            tx.run(
                """
                MATCH (f:FlowNode {tenant_id: $tenant_id, agent_id: $agent_id, flow_id: $flow_id, node_id: $canvas_node_id})
                MATCH (sp:Specialist {tenant_id: $tenant_id, agent_id: $agent_id, external_id: $sp_external_id})
                MERGE (f)-[:HAS_SPECIALIST {tenant_id: $tenant_id, agent_id: $agent_id}]->(sp)
                """,
                tenant_id=tenant_id,
                agent_id=agent_id,
                flow_id=flow_id,
                canvas_node_id=canvas_node_id,
                sp_external_id=sp_external_id,
            )
        for community in (community_rows if _extended else []):
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
        if _extended and diagnostic_row is not None:
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
