"""Семантический поиск по unified graph (узлы + pgvector), с расширением по рёбрам и mix с чанками БЗ."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal
from uuid import UUID

import structlog
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_unified_graph_node import AgentUnifiedGraphNode
from app.db.models.agent_unified_graph_relation import AgentUnifiedGraphRelation
from app.services.directory.service import create_embedding
from app.services.knowledge_files import search_indexed_knowledge_files

logger = structlog.get_logger(__name__)

_MAX_EMBED_TEXT = 8000
_MAX_PROPS_JSON = 2400
_LEXICAL_QUERY_MAX = 200


def _ilike_pattern(raw: str) -> str:
    """Безопасный шаблон для ILIKE: экранируем % и _ ."""
    s = raw.strip()[:_LEXICAL_QUERY_MAX].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{s}%"


async def _lexical_search_nodes(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    query: str,
    limit: int,
    exclude: set[str],
) -> list[AgentUnifiedGraphNode]:
    q = (query or "").strip()
    if len(q) < 2 or limit <= 0:
        return []
    pat = _ilike_pattern(q)
    stmt = (
        select(AgentUnifiedGraphNode)
        .where(
            AgentUnifiedGraphNode.tenant_id == tenant_id,
            AgentUnifiedGraphNode.agent_id == agent_id,
            or_(
                AgentUnifiedGraphNode.title.ilike(pat, escape="\\"),
                AgentUnifiedGraphNode.description.ilike(pat, escape="\\"),
                AgentUnifiedGraphNode.graph_node_id.ilike(pat, escape="\\"),
            ),
        )
        .limit(min(limit * 4, 120))
    )
    rows = (await db.execute(stmt)).scalars().all()
    out: list[AgentUnifiedGraphNode] = []
    for n in rows:
        if n.graph_node_id in exclude:
            continue
        out.append(n)
        if len(out) >= limit:
            break
    return out


def build_node_embedding_text(node: AgentUnifiedGraphNode) -> str:
    props = json.dumps(node.properties or {}, ensure_ascii=False)
    if len(props) > _MAX_PROPS_JSON:
        props = props[: _MAX_PROPS_JSON] + "…"
    parts = [
        node.entity_type,
        node.title,
        (node.description or "").strip(),
        f"origin={node.origin_slice}",
        props,
    ]
    out = "\n".join(p for p in parts if p).strip()
    return out[:_MAX_EMBED_TEXT]


def embedding_text_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def sync_unified_graph_node_embeddings(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    openai_api_key: str | None,
) -> dict[str, int]:
    """Пересчитывает эмбеддинги узлов, у которых изменился текст или вектор отсутствует."""
    if not openai_api_key:
        logger.warning("unified_graph_embedding_sync_skipped_no_key", agent_id=str(agent_id))
        return {"updated": 0, "unchanged": 0, "total": 0}

    rows = (
        (
            await db.execute(
                select(AgentUnifiedGraphNode).where(
                    AgentUnifiedGraphNode.tenant_id == tenant_id,
                    AgentUnifiedGraphNode.agent_id == agent_id,
                )
            )
        )
        .scalars()
        .all()
    )
    total = len(rows)
    unchanged = 0
    updated = 0
    for node in rows:
        embed_text = build_node_embedding_text(node)
        h = embedding_text_hash(embed_text)
        if node.embedding is not None and node.embedding_content_hash == h:
            unchanged += 1
            continue
        vec = await create_embedding(
            embed_text,
            openai_api_key=openai_api_key,
            db=db,
            tenant_id=tenant_id,
            charge_source_type="embedding.unified_graph_node",
            charge_source_id=str(node.id),
            charge_metadata={"agent_id": str(agent_id), "graph_node_id": node.graph_node_id},
        )
        if not vec:
            logger.warning(
                "unified_graph_node_embedding_failed",
                graph_node_id=node.graph_node_id,
            )
            continue
        await db.execute(
            update(AgentUnifiedGraphNode)
            .where(AgentUnifiedGraphNode.id == node.id)
            .values(embedding=vec, embedding_content_hash=h),
        )
        updated += 1

    await db.commit()
    return {"updated": updated, "unchanged": unchanged, "total": total}


async def count_embedded_nodes(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
) -> tuple[int, int]:
    total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(AgentUnifiedGraphNode)
                .where(
                    AgentUnifiedGraphNode.tenant_id == tenant_id,
                    AgentUnifiedGraphNode.agent_id == agent_id,
                )
            )
        ).scalar()
        or 0
    )
    with_emb = int(
        (
            await db.execute(
                select(func.count())
                .select_from(AgentUnifiedGraphNode)
                .where(
                    AgentUnifiedGraphNode.tenant_id == tenant_id,
                    AgentUnifiedGraphNode.agent_id == agent_id,
                    AgentUnifiedGraphNode.embedding.isnot(None),
                )
            )
        ).scalar()
        or 0
    )
    return total, with_emb


async def semantic_search_nodes(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    query: str,
    openai_api_key: str | None,
    limit: int,
) -> list[tuple[AgentUnifiedGraphNode, float]]:
    """Векторный top-K; недостающие слоты и точные совпадения по подстроке — ILIKE fallback."""
    q = (query or "").strip()
    if not q or limit <= 0:
        return []

    ordered: list[tuple[AgentUnifiedGraphNode, float]] = []
    seen: set[str] = set()

    if openai_api_key:
        q_emb = await create_embedding(
            q,
            openai_api_key=openai_api_key,
            db=db,
            tenant_id=tenant_id,
            charge_source_type="embedding.unified_graph_query",
            charge_metadata={"agent_id": str(agent_id)},
        )
        if q_emb:
            emb_str = "[" + ",".join(str(x) for x in q_emb) + "]"
            sql = text(
                """
                SELECT id, 1 - (embedding <=> CAST(:embedding AS vector)) AS score
                FROM agent_unified_graph_nodes
                WHERE tenant_id = :tenant_id
                  AND agent_id = :agent_id
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
                """
            )
            id_rows = (
                await db.execute(
                    sql,
                    {
                        "tenant_id": tenant_id,
                        "agent_id": agent_id,
                        "embedding": emb_str,
                        "limit": limit,
                    },
                )
            ).fetchall()
            if id_rows:
                ids = [row.id for row in id_rows]
                score_by_id = {row.id: float(row.score) if row.score is not None else 0.0 for row in id_rows}
                nodes = (
                    (
                        await db.execute(select(AgentUnifiedGraphNode).where(AgentUnifiedGraphNode.id.in_(ids)))
                    )
                    .scalars()
                    .all()
                )
                node_by_id = {n.id: n for n in nodes}
                for nid in ids:
                    n = node_by_id.get(nid)
                    if n and n.graph_node_id not in seen:
                        ordered.append((n, score_by_id.get(nid, 0.0)))
                        seen.add(n.graph_node_id)

    remaining = limit - len(ordered)
    if remaining > 0:
        lex_nodes = await _lexical_search_nodes(
            db,
            tenant_id=tenant_id,
            agent_id=agent_id,
            query=q,
            limit=remaining,
            exclude=seen,
        )
        for n in lex_nodes:
            if n.graph_node_id not in seen:
                ordered.append((n, 0.12))
                seen.add(n.graph_node_id)

    return ordered[:limit]


async def lightrag_style_search(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    query: str,
    openai_api_key: str | None,
    mode: Literal["nodes", "nodes_expand", "mix"],
    top_k: int,
    chunk_top_k: int,
    neighbor_edge_cap: int,
) -> dict[str, Any]:
    """
    nodes — только векторные попадания по узлам.
    nodes_expand — сиды + соседи по рёбрам (локальный подграф).
    mix — nodes_expand + семантические чанки базы знаний (как LightRAG mix).
    """
    seeds = await semantic_search_nodes(
        db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        query=query,
        openai_api_key=openai_api_key,
        limit=top_k,
    )
    seed_ids = {n.graph_node_id for n, _ in seeds}
    expanded_nodes: list[AgentUnifiedGraphNode] = []
    relations_out: list[AgentUnifiedGraphRelation] = []
    chunks: list[dict[str, Any]] = []

    if mode in ("nodes_expand", "mix") and seed_ids:
        rel_stmt = (
            select(AgentUnifiedGraphRelation)
            .where(
                AgentUnifiedGraphRelation.tenant_id == tenant_id,
                AgentUnifiedGraphRelation.agent_id == agent_id,
                or_(
                    AgentUnifiedGraphRelation.source_graph_node_id.in_(seed_ids),
                    AgentUnifiedGraphRelation.target_graph_node_id.in_(seed_ids),
                ),
            )
            .limit(neighbor_edge_cap)
        )
        relations_out = (await db.execute(rel_stmt)).scalars().all()
        neighbor_ids: set[str] = set()
        for r in relations_out:
            neighbor_ids.add(r.source_graph_node_id)
            neighbor_ids.add(r.target_graph_node_id)
        neighbor_ids -= seed_ids
        if neighbor_ids:
            n_stmt = select(AgentUnifiedGraphNode).where(
                AgentUnifiedGraphNode.tenant_id == tenant_id,
                AgentUnifiedGraphNode.agent_id == agent_id,
                AgentUnifiedGraphNode.graph_node_id.in_(neighbor_ids),
            )
            expanded_nodes = (await db.execute(n_stmt)).scalars().all()

    if mode == "mix" and chunk_top_k > 0:
        chunks = await search_indexed_knowledge_files(
            db,
            tenant_id=tenant_id,
            agent_id=agent_id,
            query=query,
            openai_api_key=openai_api_key,
            limit=chunk_top_k,
        )

    total, with_emb = await count_embedded_nodes(db, tenant_id=tenant_id, agent_id=agent_id)

    return {
        "seeds": seeds,
        "expanded_nodes": expanded_nodes,
        "relations": relations_out,
        "chunks": chunks,
        "indexed_nodes": with_emb,
        "total_nodes": total,
    }
