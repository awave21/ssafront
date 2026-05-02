"""Stage 4: cluster low-relevance queries to surface coverage-gap topics.

Approach (deliberately simple, no extra deps):
- Pull all queries with score < HIGH or zero hits in the period.
- Embed them via OpenAI (re-using existing tenant LLM config).
- Greedy clustering by cosine similarity (≥0.78 → same cluster).
- One LLM call per cluster to generate a human-readable label and suggestion.

Result is persisted into `script_flow_coverage_gap_clusters` and shown on the
coverage dashboard. The expert sees 5-10 topics instead of hundreds of rows.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.script_flow_coverage_gap_cluster import ScriptFlowCoverageGapCluster
from app.db.models.script_flow_tactic_search import ScriptFlowTacticSearch
from app.services.directory.service import create_embedding
from app.services.tenant_llm_config import get_decrypted_api_key

log = structlog.get_logger(__name__)

CLUSTER_SIMILARITY_THRESHOLD = 0.65
MIN_CLUSTER_SIZE = 2
MAX_QUERIES = 200


def _cosine(a: list[float], b: list[float]) -> float:
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return s / (na * nb)


async def _label_cluster_with_llm(
    *,
    openai_api_key: str,
    sample_queries: list[str],
) -> tuple[str, str | None]:
    """Ask LLM for a short topic label and a suggestion for the expert.

    Returns (label, suggestion). Falls back to a deterministic label if LLM
    fails — clustering must not break on LLM errors.
    """
    from app.services.runtime.model_resolver import resolve_openai_client
    from app.core.config import get_settings

    settings = get_settings()
    model = settings.summary_model or "gpt-4o-mini"
    if isinstance(model, str) and model.startswith("openai:"):
        model = model.split(":", 1)[1]
    examples = "\n".join(f"- {q}" for q in sample_queries[:8])
    prompt = (
        "Дан список похожих вопросов клиентов медицинской клиники, "
        "по которым у нас НЕТ готовых тактических сценариев. "
        "Сформулируй короткое название темы (3-6 слов) и одно предложение "
        "с рекомендацией эксперту, какой сценарий стоит написать.\n\n"
        f"Вопросы:\n{examples}\n\n"
        "Ответ строго в JSON: "
        '{"label": "<тема>", "suggestion": "<рекомендация>"}'
    )

    try:
        client = resolve_openai_client(openai_api_key=openai_api_key)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        label = (data.get("label") or "").strip()
        suggestion = (data.get("suggestion") or "").strip() or None
        if not label:
            label = sample_queries[0][:80]
        return label[:200], suggestion
    except Exception as exc:  # noqa: BLE001
        log.warning("gap_cluster.label_llm_failed", error=str(exc))
        return (sample_queries[0][:80], None)


async def recompute_gap_clusters(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    period_days: int = 7,
    score_threshold: float = 0.65,
) -> int:
    """Recompute and persist coverage-gap clusters for an agent.

    Returns the number of clusters produced.
    """
    api_key = await get_decrypted_api_key(db, tenant_id, "openai")
    if not api_key:
        log.warning("gap_cluster.no_api_key", tenant_id=str(tenant_id))
        return 0

    since = datetime.now(timezone.utc) - timedelta(days=period_days)

    # De-duplicated queries below threshold
    stmt = (
        select(
            ScriptFlowTacticSearch.query,
            func.avg(ScriptFlowTacticSearch.top_score).label("avg_score"),
            func.count().label("occurrences"),
        )
        .where(
            ScriptFlowTacticSearch.tenant_id == tenant_id,
            ScriptFlowTacticSearch.agent_id == agent_id,
            ScriptFlowTacticSearch.created_at >= since,
            (
                (ScriptFlowTacticSearch.top_score < score_threshold)
                | (ScriptFlowTacticSearch.hit_count == 0)
            ),
        )
        .group_by(ScriptFlowTacticSearch.query)
        .order_by(desc("occurrences"))
        .limit(MAX_QUERIES)
    )
    rows = (await db.execute(stmt)).all()

    if not rows:
        # Clear out old clusters even if there's nothing to compute now
        await db.execute(
            delete(ScriptFlowCoverageGapCluster).where(
                ScriptFlowCoverageGapCluster.tenant_id == tenant_id,
                ScriptFlowCoverageGapCluster.agent_id == agent_id,
            )
        )
        await db.commit()
        return 0

    # Embed each unique query
    embeddings: list[list[float]] = []
    queries: list[dict[str, Any]] = []
    for r in rows:
        emb = await create_embedding(
            r.query,
            openai_api_key=api_key,
            db=db,
            tenant_id=tenant_id,
            charge_source_type="embedding.tactic_gap_cluster",
            charge_metadata={"agent_id": str(agent_id)},
        )
        if emb is None:
            continue
        embeddings.append(emb)
        queries.append(
            {
                "query": r.query,
                "avg_score": float(r.avg_score or 0.0),
                "occurrences": int(r.occurrences),
            }
        )

    if not queries:
        return 0

    # Greedy clustering
    n = len(queries)
    assigned = [-1] * n
    cluster_id = 0
    for i in range(n):
        if assigned[i] != -1:
            continue
        assigned[i] = cluster_id
        for j in range(i + 1, n):
            if assigned[j] != -1:
                continue
            if _cosine(embeddings[i], embeddings[j]) >= CLUSTER_SIMILARITY_THRESHOLD:
                assigned[j] = cluster_id
        cluster_id += 1

    # Group
    groups: dict[int, list[int]] = {}
    for idx, c in enumerate(assigned):
        groups.setdefault(c, []).append(idx)

    # Wipe previous clusters for this agent before saving fresh ones
    await db.execute(
        delete(ScriptFlowCoverageGapCluster).where(
            ScriptFlowCoverageGapCluster.tenant_id == tenant_id,
            ScriptFlowCoverageGapCluster.agent_id == agent_id,
        )
    )

    now = datetime.now(timezone.utc)
    saved = 0
    # Sort clusters by total occurrences (most-frequent gaps first)
    ordered = sorted(
        groups.items(),
        key=lambda kv: -sum(queries[i]["occurrences"] for i in kv[1]),
    )

    for _cid, idxs in ordered:
        # Skip noise/singletons unless they occur multiple times
        cluster_queries = [queries[i] for i in idxs]
        total_occ = sum(q["occurrences"] for q in cluster_queries)
        if len(idxs) < MIN_CLUSTER_SIZE and total_occ < 2:
            continue

        sample = sorted(cluster_queries, key=lambda q: -q["occurrences"])[:6]
        avg_score = sum(q["avg_score"] for q in cluster_queries) / max(
            1, len(cluster_queries)
        )

        label, suggestion = await _label_cluster_with_llm(
            openai_api_key=api_key,
            sample_queries=[q["query"] for q in sample],
        )

        row = ScriptFlowCoverageGapCluster(
            tenant_id=tenant_id,
            agent_id=agent_id,
            period_days=period_days,
            label=label,
            suggestion=suggestion,
            query_count=len(idxs),
            avg_score=avg_score,
            sample_queries=[
                {
                    "query": q["query"],
                    "occurrences": q["occurrences"],
                    "avg_score": round(q["avg_score"], 3),
                }
                for q in sample
            ],
            created_at=now,
        )
        db.add(row)
        saved += 1

    await db.commit()
    log.info(
        "gap_cluster.recompute.done",
        agent_id=str(agent_id),
        clusters=saved,
        queries=len(queries),
    )
    return saved


async def get_latest_clusters(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(ScriptFlowCoverageGapCluster)
            .where(
                ScriptFlowCoverageGapCluster.tenant_id == tenant_id,
                ScriptFlowCoverageGapCluster.agent_id == agent_id,
            )
            .order_by(desc(ScriptFlowCoverageGapCluster.query_count))
        )
    ).scalars().all()

    return [
        {
            "id": str(r.id),
            "label": r.label,
            "suggestion": r.suggestion,
            "query_count": r.query_count,
            "avg_score": round(r.avg_score, 3) if r.avg_score is not None else None,
            "sample_queries": list(r.sample_queries or []),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
