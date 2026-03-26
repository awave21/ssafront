from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.directory.service import _text_overlap_score, create_embedding

# Сколько кандидатов забрать из БД до rerank (limit * multiplier).
_RERANK_CANDIDATES_MULTIPLIER = 4
# Вес векторного score в финальном гибридном score.
_RERANK_VECTOR_WEIGHT = 0.65


def _rerank_direct_question_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    vector_weight: float = _RERANK_VECTOR_WEIGHT,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """
    Гибридный rerank: комбинирует векторный score с лексическим перекрытием по title.

    Не требует дополнительных API-вызовов — работает на уже полученных кандидатах.
    """
    text_weight = 1.0 - vector_weight
    q = query.lower()
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in candidates:
        title = str(item.get("title", "")).lower()
        text_score = _text_overlap_score(q, title)
        combined = vector_weight * float(item["relevance"]) + text_weight * text_score
        scored.append((combined, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    reranked = [
        {**item, "relevance": round(score, 4), "match_percent": round(min(score, 1.0) * 100, 2)}
        for score, item in scored
    ]
    return reranked[:top_n] if top_n else reranked


async def search_direct_question_candidates(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    query: str,
    openai_api_key: str | None,
    limit: int = 5,
    min_match_percent: int = 45,
    rerank: bool = True,
    rerank_vector_weight: float = _RERANK_VECTOR_WEIGHT,
    rerank_candidates_multiplier: int = _RERANK_CANDIDATES_MULTIPLIER,
) -> dict[str, Any]:
    query_clean = str(query or "").strip()
    if not query_clean:
        return {"status": "no_match", "candidates": [], "chosen_candidate_id": None}

    normalized_limit = max(1, min(int(limit or 5), 20))
    min_score = max(0.0, min(float(min_match_percent) / 100.0, 1.0))

    # Берём больше кандидатов для rerank, потом обрезаем до limit.
    fetch_limit = normalized_limit * rerank_candidates_multiplier if rerank else normalized_limit

    query_embedding = await create_embedding(
        query_clean,
        openai_api_key=openai_api_key,
        db=db,
        tenant_id=tenant_id,
        charge_source_type="embedding.direct_question_query",
        charge_metadata={"agent_id": str(agent_id)},
    )
    if query_embedding is None:
        return {
            "status": "error",
            "error": "query_embedding_unavailable",
            "candidates": [],
            "chosen_candidate_id": None,
        }

    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    sql = text(
        """
        SELECT
            id,
            title,
            1 - (embedding <=> CAST(:embedding AS vector)) AS relevance
        FROM direct_questions
        WHERE tenant_id = :tenant_id
          AND agent_id = :agent_id
          AND is_enabled = true
          AND embedding IS NOT NULL
          AND embedding_status = 'ready'
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
                "limit": fetch_limit,
            },
        )
    ).fetchall()

    candidates: list[dict[str, Any]] = [
        {
            "id": str(row.id),
            "title": str(row.title or ""),
            "relevance": float(row.relevance) if row.relevance is not None else 0.0,
            "match_percent": round(max(0.0, min(float(row.relevance or 0.0), 1.0)) * 100, 2),
        }
        for row in rows
    ]

    # Rerank: гибридный score (вектор + лексическое перекрытие по title).
    if rerank and len(candidates) > 1:
        candidates = _rerank_direct_question_candidates(
            query_clean,
            candidates,
            vector_weight=rerank_vector_weight,
            top_n=normalized_limit,
        )
    else:
        candidates = candidates[:normalized_limit]

    matched = [item for item in candidates if float(item["relevance"]) >= min_score]
    chosen_id = matched[0]["id"] if matched else None
    return {
        "status": "ok" if chosen_id else "no_match",
        "candidates": candidates,
        "matched": matched,
        "chosen_candidate_id": chosen_id,
        "min_match_percent": int(min_match_percent),
    }
