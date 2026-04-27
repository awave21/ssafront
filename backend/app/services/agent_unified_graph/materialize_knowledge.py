from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_unified_graph_node import AgentUnifiedGraphNode
from app.db.models.agent_unified_graph_relation import AgentUnifiedGraphRelation
from app.db.models.knowledge_file import KnowledgeFile
from app.db.models.knowledge_file_chunk import KnowledgeFileChunk
from app.services.agent_unified_graph import ontology as uo
from app.services.agent_unified_graph.stable_node_ids import knowledge_chunk_node_id, knowledge_file_node_id

logger = structlog.get_logger(__name__)

_FILE_ID_JSON = AgentUnifiedGraphNode.properties["knowledge_file_id"].astext


async def materialize_knowledge_file_unified_graph(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    file_id: UUID,
) -> None:
    """Структурный срез БЗ: файл и чанки + рёбра CONTAINS (gold, без LLM).

    Вызывается после успешной векторной индексации файла.
    """
    await db.execute(
        delete(AgentUnifiedGraphRelation).where(
            and_(
                AgentUnifiedGraphRelation.agent_id == agent_id,
                AgentUnifiedGraphRelation.origin_slice == uo.ORIGIN_KNOWLEDGE,
                AgentUnifiedGraphRelation.properties["knowledge_file_id"].astext == str(file_id),
            )
        )
    )
    await db.execute(
        delete(AgentUnifiedGraphNode).where(
            and_(
                AgentUnifiedGraphNode.agent_id == agent_id,
                AgentUnifiedGraphNode.origin_slice == uo.ORIGIN_KNOWLEDGE,
                _FILE_ID_JSON == str(file_id),
            )
        )
    )

    file_row = (
        await db.execute(
            select(KnowledgeFile).where(
                KnowledgeFile.id == file_id,
                KnowledgeFile.agent_id == agent_id,
                KnowledgeFile.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if file_row is None or file_row.type != "file":
        return

    chunks = (
        (
            await db.execute(
                select(KnowledgeFileChunk)
                .where(KnowledgeFileChunk.file_id == file_id)
                .order_by(KnowledgeFileChunk.chunk_index.asc())
            )
        )
        .scalars()
        .all()
    )

    file_gid = knowledge_file_node_id(file_row.id)
    db.add(
        AgentUnifiedGraphNode(
            tenant_id=tenant_id,
            agent_id=agent_id,
            origin_slice=uo.ORIGIN_KNOWLEDGE,
            graph_node_id=file_gid,
            entity_type=uo.ENTITY_KNOWLEDGE_FILE,
            title=(file_row.title or "Knowledge file")[:500],
            description=None,
            domain_entity_id=file_row.id,
            properties={
                "knowledge_file_id": str(file_id),
                "kind": "file",
                "meta_tags": file_row.meta_tags or [],
            },
            provenance_tier=uo.PROVENANCE_GOLD,
        )
    )

    for ch in chunks:
        chunk_gid = knowledge_chunk_node_id(ch.id)
        preview = (ch.chunk_text or "").strip().replace("\n", " ")[:2000]
        db.add(
            AgentUnifiedGraphNode(
                tenant_id=tenant_id,
                agent_id=agent_id,
                origin_slice=uo.ORIGIN_KNOWLEDGE,
                graph_node_id=chunk_gid,
                entity_type=uo.ENTITY_KNOWLEDGE_CHUNK,
                title=f"{(file_row.title or 'Chunk')[:200]} · #{ch.chunk_index}"[:500],
                description=preview or None,
                domain_entity_id=ch.id,
                properties={
                    "knowledge_file_id": str(file_id),
                    "chunk_index": ch.chunk_index,
                    "kind": "chunk",
                },
                provenance_tier=uo.PROVENANCE_GOLD,
            )
        )
        db.add(
            AgentUnifiedGraphRelation(
                tenant_id=tenant_id,
                agent_id=agent_id,
                origin_slice=uo.ORIGIN_KNOWLEDGE,
                source_graph_node_id=file_gid,
                target_graph_node_id=chunk_gid,
                relation_type=uo.REL_KNOWLEDGE_FILE_CONTAINS_CHUNK,
                weight=1.0,
                properties={"knowledge_file_id": str(file_id)},
                provenance_tier=uo.PROVENANCE_GOLD,
            )
        )

    await db.flush()
    logger.info(
        "agent_unified_graph_knowledge_materialized",
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        file_id=str(file_id),
        chunks=len(chunks),
    )
