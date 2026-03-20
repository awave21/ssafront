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

    if openai_api_key:
        query_embedding = await create_embedding(
            query_clean,
            openai_api_key=openai_api_key,
            db=db,
            tenant_id=tenant_id,
            charge_source_type="embedding.knowledge_query",
            charge_metadata={"agent_id": str(agent_id)},
        )
    else:
        query_embedding = None

    if query_embedding:
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        sql = text(
            """
            SELECT
                id,
                title,
                content,
                meta_tags,
                1 - (embedding <=> CAST(:embedding AS vector)) AS relevance
            FROM knowledge_files
            WHERE tenant_id = :tenant_id
              AND agent_id = :agent_id
              AND type = 'file'
              AND is_enabled = true
              AND vector_status = 'indexed'
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
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
                "id": str(row.id),
                "title": row.title,
                "content": row.content,
                "meta_tags": row.meta_tags or [],
                "relevance": float(row.relevance) if row.relevance is not None else 0.0,
            }
            for row in rows
        ]

    fallback_sql = text(
        """
        SELECT
            id,
            title,
            content,
            meta_tags
        FROM knowledge_files
        WHERE tenant_id = :tenant_id
          AND agent_id = :agent_id
          AND type = 'file'
          AND is_enabled = true
          AND (
            title ILIKE :query
            OR content ILIKE :query
          )
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT :limit
        """
    )
    rows = (
        await db.execute(
            fallback_sql,
            {
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "query": f"%{query_clean}%",
                "limit": limit,
            },
        )
    ).fetchall()
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "content": row.content,
            "meta_tags": row.meta_tags or [],
            "relevance": 0.5,
        }
        for row in rows
    ]
