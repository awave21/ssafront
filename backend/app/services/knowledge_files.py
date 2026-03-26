from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.directory.service import create_embedding


async def search_indexed_knowledge_files(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    query: str,
    openai_api_key: str | None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    query_clean = str(query or "").strip()
    if not query_clean:
        return []

    if not openai_api_key:
        return []

    query_embedding = await create_embedding(
        query_clean,
        openai_api_key=openai_api_key,
        db=db,
        tenant_id=tenant_id,
        charge_source_type="embedding.knowledge_query",
        charge_metadata={"agent_id": str(agent_id)},
    )
    if not query_embedding:
        return []

    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    sql = text(
        """
        SELECT
            kfc.id AS chunk_id,
            kfc.chunk_index AS chunk_index,
            kfc.chunk_text AS content,
            kf.id AS file_id,
            kf.title,
            meta_tags,
            1 - (kfc.embedding <=> CAST(:embedding AS vector)) AS relevance
        FROM knowledge_file_chunks kfc
        JOIN knowledge_files kf ON kf.id = kfc.file_id
        WHERE kf.tenant_id = :tenant_id
          AND kf.agent_id = :agent_id
          AND kf.type = 'file'
          AND kf.is_enabled = true
          AND kf.vector_status = 'indexed'
          AND kfc.embedding IS NOT NULL
        ORDER BY kfc.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
        """
    )
    rows = (
        await db.execute(
            sql,
            {
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "embedding": embedding_str,
                "limit": limit,
            },
        )
    ).fetchall()
    return [
        {
            "id": str(row.chunk_id),
            "file_id": str(row.file_id),
            "chunk_index": int(row.chunk_index) if row.chunk_index is not None else None,
            "title": row.title,
            "content": row.content,
            "meta_tags": row.meta_tags or [],
            "relevance": float(row.relevance) if row.relevance is not None else 0.0,
        }
        for row in rows
    ]
