"""Одноразовый импорт GraphRAG parquet entities/relationships → Neo4j.

Читает output/entities.parquet и output/relationships.parquet из локального
GraphRAG workspace и создаёт :GraphNode + :HAS_SEMANTIC рёбра в Neo4j.
Дополнительно fuzzy-match PERSON → :Specialist и SERVICE → :Service.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_ENTITY_TYPE_MAP = {
    "SERVICE": "service",
    "PERSON": "specialist",
    "PRODUCT/BRAND": "product",
    "ORGANIZATION": "organization",
}

_FUZZY_SERVICE_THRESHOLD = 0.75
_FUZZY_SPECIALIST_THRESHOLD = 0.80


def _map_entity_type(raw_type: str) -> str:
    return _ENTITY_TYPE_MAP.get((raw_type or "").upper().strip(), "entity")


async def import_graphrag_parquet_to_neo4j(
    *,
    tenant_id: UUID,
    agent_id: UUID,
    db: AsyncSession,
    openai_api_key: str | None = None,
) -> dict[str, int]:
    """Импортирует GraphRAG parquet entities/relationships в Neo4j.

    Возвращает статистику: nodes_created, edges_created, fuzzy_links.
    """
    from app.core.config import get_settings
    from app.db.models.agent import Agent
    from app.services.graphrag_export.graphrag_preview import agent_graphrag_workspace
    from app.services.runtime.neo4j_client import get_neo4j_driver

    settings = get_settings()
    if not settings.neo4j_enabled:
        logger.info("parquet_import_skipped_neo4j_disabled")
        return {"nodes_created": 0, "edges_created": 0, "fuzzy_links": 0}

    driver = get_neo4j_driver()
    if driver is None:
        logger.warning("parquet_import_skipped_no_driver")
        return {"nodes_created": 0, "edges_created": 0, "fuzzy_links": 0}

    from sqlalchemy import select
    agent = (await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if agent is None:
        logger.warning("parquet_import_agent_not_found", agent_id=str(agent_id))
        return {"nodes_created": 0, "edges_created": 0, "fuzzy_links": 0}

    ws = agent_graphrag_workspace(settings, tenant_id=tenant_id, agent=agent)
    if ws is None or not ws.is_dir():
        logger.warning("parquet_import_no_workspace", agent_id=str(agent_id))
        return {"nodes_created": 0, "edges_created": 0, "fuzzy_links": 0}

    out_dir = ws / "output"
    if not out_dir.is_dir():
        logger.warning("parquet_import_no_output_dir", path=str(out_dir))
        return {"nodes_created": 0, "edges_created": 0, "fuzzy_links": 0}

    try:
        import pandas as pd
    except ImportError:
        logger.error("parquet_import_pandas_missing")
        return {"nodes_created": 0, "edges_created": 0, "fuzzy_links": 0}

    # Load entities
    entities_path = _first_file(out_dir, ("entities.parquet", "create_final_entities.parquet"))
    if entities_path is None:
        logger.warning("parquet_import_no_entities_file", dir=str(out_dir))
        return {"nodes_created": 0, "edges_created": 0, "fuzzy_links": 0}

    try:
        ent_df = pd.read_parquet(entities_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("parquet_import_entities_read_failed", error=str(exc))
        return {"nodes_created": 0, "edges_created": 0, "fuzzy_links": 0}

    tenant_id_str = str(tenant_id)
    agent_id_str = str(agent_id)

    # Build node rows
    node_rows: list[dict[str, Any]] = []
    id_to_gid: dict[str, str] = {}  # parquet entity id → graph_node_id
    for _, row in ent_df.iterrows():
        raw_id = str(row.get("id") or row.get("human_readable_id") or "").strip()
        if not raw_id:
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        description = str(row.get("description") or "").strip()
        raw_type = str(row.get("type") or "").strip()
        entity_type = _map_entity_type(raw_type)
        graph_node_id = f"parquet:{raw_id}"
        id_to_gid[raw_id] = graph_node_id
        node_rows.append({
            "graph_node_id": graph_node_id,
            "title": title,
            "description": description,
            "content_text": description,
            "entity_type": entity_type,
            "raw_type": raw_type,
        })

    if not node_rows:
        logger.info("parquet_import_no_nodes", agent_id=agent_id_str)
        return {"nodes_created": 0, "edges_created": 0, "fuzzy_links": 0}

    # Compute embeddings in batch
    texts = [f"{n['title']} {n['description']}".strip() for n in node_rows]
    embeddings: list[list[float] | None] = [None] * len(node_rows)
    if openai_api_key:
        try:
            from app.services.directory.service import create_embeddings_batch
            embeddings = await create_embeddings_batch(
                texts,
                openai_api_key=openai_api_key,
                db=db,
                tenant_id=tenant_id,
                charge_source_type="embedding.parquet_import",
                charge_source_id=agent_id_str,
                charge_metadata={"agent_id": agent_id_str},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("parquet_import_embeddings_failed", error=str(exc))

    for i, n in enumerate(node_rows):
        n["embedding"] = embeddings[i] if i < len(embeddings) else None

    # Write nodes to Neo4j
    database = settings.neo4j_database or None
    nodes_created = 0

    def _write_nodes(tx: Any) -> int:
        count = 0
        for n in node_rows:
            tx.run(
                """
                MERGE (g:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, graph_node_id: $graph_node_id})
                SET g:Searchable,
                    g.node_kind = 'entity',
                    g.entity_type = $entity_type,
                    g.title = $title,
                    g.description = $description,
                    g.content_text = $content_text,
                    g.flow_id = '',
                    g.flow_version = 0,
                    g.source_node_ids = [],
                    g.community_key = '',
                    g.properties = $raw_type,
                    g.embedding = $embedding
                """,
                tenant_id=tenant_id_str,
                agent_id=agent_id_str,
                graph_node_id=n["graph_node_id"],
                entity_type=n["entity_type"],
                title=n["title"],
                description=n["description"],
                content_text=n["content_text"],
                raw_type=n["raw_type"],
                embedding=n["embedding"],
            )
            count += 1
        return count

    try:
        with driver.session(database=database) as session:
            nodes_created = session.execute_write(_write_nodes)
        logger.info("parquet_import_nodes_written", count=nodes_created, agent_id=agent_id_str)
    except Exception as exc:  # noqa: BLE001
        logger.error("parquet_import_nodes_write_failed", error=str(exc))
        return {"nodes_created": 0, "edges_created": 0, "fuzzy_links": 0}

    # Load and write relationships
    edges_created = 0
    rels_path = _first_file(out_dir, ("relationships.parquet", "create_final_relationships.parquet"))
    if rels_path is not None:
        try:
            rel_df = pd.read_parquet(rels_path)
            edge_rows: list[dict[str, str]] = []
            for _, row in rel_df.iterrows():
                src = str(row.get("source") or "").strip()
                tgt = str(row.get("target") or "").strip()
                desc = str(row.get("description") or "")[:200]
                if not src or not tgt:
                    continue
                # IDs in relationships.parquet refer to entity titles (human_readable_id)
                src_gid = id_to_gid.get(src) or f"parquet:{src}"
                tgt_gid = id_to_gid.get(tgt) or f"parquet:{tgt}"
                edge_rows.append({"src_gid": src_gid, "tgt_gid": tgt_gid, "relation_type": desc})

            def _write_edges(tx: Any) -> int:
                count = 0
                for e in edge_rows:
                    result = tx.run(
                        """
                        MATCH (s:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, graph_node_id: $src_gid})
                        MATCH (t:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, graph_node_id: $tgt_gid})
                        MERGE (s)-[r:HAS_SEMANTIC {tenant_id: $tenant_id, agent_id: $agent_id,
                                                    src_gid: $src_gid, tgt_gid: $tgt_gid}]->(t)
                        SET r.relation_type = $relation_type
                        RETURN count(r) AS cnt
                        """,
                        tenant_id=tenant_id_str,
                        agent_id=agent_id_str,
                        **e,
                    )
                    count += 1
                return count

            with driver.session(database=database) as session:
                edges_created = session.execute_write(_write_edges)
            logger.info("parquet_import_edges_written", count=edges_created, agent_id=agent_id_str)
        except Exception as exc:  # noqa: BLE001
            logger.warning("parquet_import_edges_failed", error=str(exc))

    # Fuzzy-match: link parquet GraphNode → existing :Service / :Specialist
    fuzzy_links = await _fuzzy_link_parquet_nodes(
        driver=driver,
        db=db,
        agent_id=agent_id,
        tenant_id=tenant_id,
        node_rows=node_rows,
        database=database,
    )

    logger.info(
        "parquet_import_done",
        agent_id=agent_id_str,
        nodes=nodes_created,
        edges=edges_created,
        fuzzy_links=fuzzy_links,
    )
    return {"nodes_created": nodes_created, "edges_created": edges_created, "fuzzy_links": fuzzy_links}


async def _fuzzy_link_parquet_nodes(
    *,
    driver: Any,
    db: AsyncSession,
    agent_id: UUID,
    tenant_id: UUID,
    node_rows: list[dict[str, Any]],
    database: str | None,
) -> int:
    from sqlalchemy import select
    from app.db.models.sqns_service import SqnsResource, SqnsService
    from app.services.runtime.graphrag_tool import _normalize_lookup_text, _score_candidate

    tenant_id_str = str(tenant_id)
    agent_id_str = str(agent_id)

    service_rows = (await db.execute(
        select(SqnsService).where(
            SqnsService.agent_id == agent_id,
            SqnsService.is_enabled.is_(True),
            SqnsService.stale_since.is_(None),
        )
    )).scalars().all()

    specialist_rows = (await db.execute(
        select(SqnsResource).where(
            SqnsResource.agent_id == agent_id,
            SqnsResource.active.is_(True),
            SqnsResource.is_active.is_(True),
        )
    )).scalars().all()

    links = 0

    def _write_links(tx: Any, pairs: list[tuple[str, str, str]]) -> int:
        count = 0
        for gid, ext_id, node_type in pairs:
            if node_type == "service":
                tx.run(
                    """
                    MATCH (g:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, graph_node_id: $gid})
                    MATCH (s:Service {tenant_id: $tenant_id, agent_id: $agent_id, external_id: $ext_id})
                    MERGE (g)-[:HAS_SEMANTIC {tenant_id: $tenant_id, agent_id: $agent_id,
                                               relation_type: 'is_service'}]->(s)
                    """,
                    tenant_id=tenant_id_str,
                    agent_id=agent_id_str,
                    gid=gid,
                    ext_id=int(ext_id),
                )
            else:
                tx.run(
                    """
                    MATCH (g:GraphNode {tenant_id: $tenant_id, agent_id: $agent_id, graph_node_id: $gid})
                    MATCH (sp:Specialist {tenant_id: $tenant_id, agent_id: $agent_id, external_id: $ext_id})
                    MERGE (g)-[:HAS_SEMANTIC {tenant_id: $tenant_id, agent_id: $agent_id,
                                               relation_type: 'is_specialist'}]->(sp)
                    """,
                    tenant_id=tenant_id_str,
                    agent_id=agent_id_str,
                    gid=gid,
                    ext_id=int(ext_id),
                )
            count += 1
        return count

    pairs: list[tuple[str, str, str]] = []
    for n in node_rows:
        title_norm = _normalize_lookup_text(n["title"])
        if n["entity_type"] == "service":
            best_score, best_id = 0.0, None
            for svc in service_rows:
                score = _score_candidate(title_norm, svc.name)
                if score > best_score:
                    best_score, best_id = score, str(svc.external_id)
            if best_score >= _FUZZY_SERVICE_THRESHOLD and best_id:
                pairs.append((n["graph_node_id"], best_id, "service"))
        elif n["entity_type"] == "specialist":
            best_score, best_id = 0.0, None
            for sp in specialist_rows:
                score = _score_candidate(title_norm, sp.name)
                if score > best_score:
                    best_score, best_id = score, str(sp.external_id)
            if best_score >= _FUZZY_SPECIALIST_THRESHOLD and best_id:
                pairs.append((n["graph_node_id"], best_id, "specialist"))

    if pairs:
        try:
            with driver.session(database=database) as session:
                links = session.execute_write(_write_links, pairs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("parquet_import_fuzzy_links_failed", error=str(exc))

    return links


def _first_file(base: Path, names: tuple[str, ...]) -> Path | None:
    for n in names:
        p = base / n
        if p.is_file():
            return p
    return None
