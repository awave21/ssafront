"""Гибридный (ILIKE/trgm + pgvector) поиск по SQNS-кэшу услуг и специалистов.

Зачем: раньше подбор услуг/врачей шёл чистым ILIKE по имени (sync.py:_find_*),
и запрос намерением («убрать морщины») не находил услугу «Ботулинотерапия».
Здесь — двухпуловый поиск: вектор (по смыслу) ∪ trigram/ILIKE (по точному имени/коду),
слияние через RRF. Возвращает стабильный external_id для threading в SQNS-тулы.

Идиомы переиспользованы из:
- app/services/direct_questions/retrieval.py  — pgvector `<=>`, порог, кандидаты
- app/services/directory/service.py            — create_embedding(s), trgm similarity
- app/services/agent_unified_graph/embeddings.py — content-hash gate (invalidation)

trigram-индексы на sqns_services/resources.name(+description) уже есть (миграция 0012);
vector-колонки + HNSW — миграция 0099.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.directory.service import create_embedding, create_embeddings_batch

logger = structlog.get_logger(__name__)

# RRF-константа: чем больше, тем «мягче» вклад ранга (стандарт ≈ 60).
_RRF_K = 60
# Сколько кандидатов тянуть из каждого пула до слияния.
_POOL_SIZE = 20
# Порог trigram-похожести для лексического пула (как в directory/_search_fuzzy).
_TRGM_THRESHOLD = 0.2


def _content_hash(text_value: str, model_signature: str) -> str:
    """Хеш для invalidation: смена модели ИЛИ текста → пересчёт эмбеддинга."""
    h = hashlib.sha256()
    h.update(model_signature.encode("utf-8"))
    h.update(b"\n")
    h.update(text_value.encode("utf-8"))
    return h.hexdigest()[:64]


def _service_embed_text(name: str | None, category: str | None, description: str | None) -> str:
    parts = [p for p in (name, category, description) if p and str(p).strip()]
    return "\n".join(str(p).strip() for p in parts)[:4000]


def _resource_embed_text(name: str | None, specialization: str | None, information: str | None) -> str:
    parts = [p for p in (name, specialization, information) if p and str(p).strip()]
    return "\n".join(str(p).strip() for p in parts)[:4000]


def _emb_literal(embedding: list[float]) -> str:
    # asyncpg не всегда корректно сериализует list[float] в vector — передаём text-литерал.
    return "[" + ",".join(str(float(x)) for x in embedding) + "]"


# ---------------------------------------------------------------------------
# Backfill / refresh эмбеддингов (хук в hourly-sync + разовый бэкфилл)
# ---------------------------------------------------------------------------

async def compute_sqns_embeddings(
    db: AsyncSession,
    *,
    agent_id: UUID,
    tenant_id: UUID,
    openai_api_key: str | None,
    max_items: int = 5000,
) -> dict[str, int]:
    """Пересчитать эмбеддинги услуг/специалистов агента с хеш-гейтом.

    Пропускает строки, чей content-hash не изменился, — поэтому дёшево гонять
    после каждого hourly-sync. Записывает vector через raw SQL (CAST из text).
    """
    settings = get_settings()
    model_sig = settings.embedding_model
    stats = {"services_embedded": 0, "services_skipped": 0,
             "resources_embedded": 0, "resources_skipped": 0}

    if not openai_api_key:
        logger.warning("sqns_embeddings_skipped_no_key", agent_id=str(agent_id))
        return stats

    async def _refresh(table: str, embed_text_fn, source_type: str, embedded_key: str, skipped_key: str) -> None:
        rows = (await db.execute(text(
            f"SELECT id, name, "
            + ("category, description" if table == "sqns_services" else "specialization, information")
            + f", embedding_content_hash AS h FROM {table} "
            "WHERE agent_id = :aid ORDER BY updated_at DESC LIMIT :lim"
        ), {"aid": agent_id, "lim": max_items})).fetchall()

        dirty: list[tuple[Any, str, str]] = []  # (id, text, hash)
        for r in rows:
            if table == "sqns_services":
                txt = embed_text_fn(r.name, r.category, r.description)
            else:
                txt = embed_text_fn(r.name, r.specialization, r.information)
            if not txt:
                stats[skipped_key] += 1
                continue
            new_hash = _content_hash(txt, model_sig)
            if r.h == new_hash:
                stats[skipped_key] += 1
                continue
            dirty.append((r.id, txt, new_hash))

        if not dirty:
            return

        embeddings = await create_embeddings_batch(
            [d[1] for d in dirty],
            openai_api_key=openai_api_key,
            db=db,
            tenant_id=tenant_id,
            charge_source_type=source_type,
            charge_metadata={"agent_id": str(agent_id)},
        )
        for (row_id, _txt, new_hash), emb in zip(dirty, embeddings):
            if emb is None:
                continue
            await db.execute(text(
                f"UPDATE {table} SET embedding = CAST(CAST(:emb AS text) AS vector), "
                "embedding_content_hash = :h WHERE id = :id"
            ), {"emb": _emb_literal(emb), "h": new_hash, "id": row_id})
            stats[embedded_key] += 1
        await db.commit()

    await _refresh("sqns_services", _service_embed_text, "embedding.sqns_service",
                   "services_embedded", "services_skipped")
    await _refresh("sqns_resources", _resource_embed_text, "embedding.sqns_resource",
                   "resources_embedded", "resources_skipped")

    logger.info("sqns_embeddings_computed", agent_id=str(agent_id), **stats)
    return stats


# ---------------------------------------------------------------------------
# Гибридный поиск (двухпуловый RRF)
# ---------------------------------------------------------------------------

def _rrf_fuse(pools: list[list[str]]) -> dict[str, float]:
    """Reciprocal Rank Fusion: score(id) = Σ 1/(k + rank) по всем пулам (rank с 1)."""
    scores: dict[str, float] = {}
    for pool in pools:
        for rank, ext_id in enumerate(pool, start=1):
            scores[ext_id] = scores.get(ext_id, 0.0) + 1.0 / (_RRF_K + rank)
    return scores


async def search_services_hybrid(
    db: AsyncSession,
    *,
    agent_id: UUID,
    query: str,
    openai_api_key: str | None,
    tenant_id: UUID | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Найти услуги по намерению: вектор ∪ trigram/ILIKE → RRF. Возвращает external_id.

    Graceful degradation: нет эмбеддинга запроса (API недоступен) → только лексика;
    услуга без embedding → всё равно находится лексикой; пусто в обоих пулах → [].
    """
    q = str(query or "").strip()
    if not q:
        return []

    base_filter = ("agent_id = :aid AND is_enabled = true AND stale_since IS NULL")
    params: dict[str, Any] = {"aid": agent_id, "q": q, "like": f"%{q}%", "k": _POOL_SIZE}

    meta: dict[str, dict[str, Any]] = {}  # external_id -> row fields

    # --- Пул A: вектор ---
    vector_pool: list[str] = []
    query_embedding = await create_embedding(
        q, openai_api_key=openai_api_key, db=db, tenant_id=tenant_id,
        charge_source_type="embedding.sqns_service_query",
        charge_metadata={"agent_id": str(agent_id)},
    ) if openai_api_key else None
    if query_embedding is not None:
        params["emb"] = _emb_literal(query_embedding)
        rows = (await db.execute(text(
            f"""
            SELECT external_id, name, category, price, duration_seconds, priority, description,
                   1 - (embedding <=> CAST(CAST(:emb AS text) AS vector)) AS vec_score
            FROM sqns_services
            WHERE {base_filter} AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(CAST(:emb AS text) AS vector)
            LIMIT :k
            """
        ), params)).fetchall()
        for r in rows:
            ext = str(r.external_id)
            vector_pool.append(ext)
            meta.setdefault(ext, _row_to_meta(r))

    # --- Пул B: лексика (trigram + ILIKE) ---
    rows = (await db.execute(text(
        f"""
        SELECT external_id, name, category, price, duration_seconds, priority, description,
               GREATEST(similarity(name, :q),
                        similarity(COALESCE(description, ''), :q)) AS lex_score
        FROM sqns_services
        WHERE {base_filter}
          AND (name ILIKE :like
               OR similarity(name, :q) > :thr
               OR similarity(COALESCE(description, ''), :q) > :thr)
        ORDER BY lex_score DESC
        LIMIT :k
        """
    ), {**params, "thr": _TRGM_THRESHOLD})).fetchall()
    lexical_pool: list[str] = []
    for r in rows:
        ext = str(r.external_id)
        lexical_pool.append(ext)
        meta.setdefault(ext, _row_to_meta(r))

    if not vector_pool and not lexical_pool:
        return []

    fused = _rrf_fuse([vector_pool, lexical_pool])
    # tie-break по priority (выше — важнее)
    ranked = sorted(
        fused.items(),
        key=lambda kv: (kv[1], meta.get(kv[0], {}).get("priority", 0)),
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for ext_id, score in ranked[:limit]:
        item = dict(meta.get(ext_id, {}))
        item["external_id"] = int(ext_id) if ext_id.lstrip("-").isdigit() else ext_id
        item["score"] = round(float(score), 6)
        out.append(item)
    return out


async def search_resources_hybrid(
    db: AsyncSession,
    *,
    agent_id: UUID,
    query: str,
    openai_api_key: str | None,
    tenant_id: UUID | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Найти специалистов по намерению (имя/специализация). Симметрично услугам."""
    q = str(query or "").strip()
    if not q:
        return []

    base_filter = "agent_id = :aid AND is_active = true AND active = true"
    params: dict[str, Any] = {"aid": agent_id, "q": q, "like": f"%{q}%", "k": _POOL_SIZE}
    meta: dict[str, dict[str, Any]] = {}

    vector_pool: list[str] = []
    query_embedding = await create_embedding(
        q, openai_api_key=openai_api_key, db=db, tenant_id=tenant_id,
        charge_source_type="embedding.sqns_resource_query",
        charge_metadata={"agent_id": str(agent_id)},
    ) if openai_api_key else None
    if query_embedding is not None:
        params["emb"] = _emb_literal(query_embedding)
        rows = (await db.execute(text(
            f"""
            SELECT external_id, name, specialization, information,
                   1 - (embedding <=> CAST(CAST(:emb AS text) AS vector)) AS vec_score
            FROM sqns_resources
            WHERE {base_filter} AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(CAST(:emb AS text) AS vector)
            LIMIT :k
            """
        ), params)).fetchall()
        for r in rows:
            ext = str(r.external_id)
            vector_pool.append(ext)
            meta.setdefault(ext, _resource_meta(r))

    rows = (await db.execute(text(
        f"""
        SELECT external_id, name, specialization, information,
               GREATEST(similarity(name, :q),
                        similarity(COALESCE(specialization, ''), :q)) AS lex_score
        FROM sqns_resources
        WHERE {base_filter}
          AND (name ILIKE :like
               OR similarity(name, :q) > :thr
               OR similarity(COALESCE(specialization, ''), :q) > :thr)
        ORDER BY lex_score DESC
        LIMIT :k
        """
    ), {**params, "thr": _TRGM_THRESHOLD})).fetchall()
    lexical_pool: list[str] = []
    for r in rows:
        ext = str(r.external_id)
        lexical_pool.append(ext)
        meta.setdefault(ext, _resource_meta(r))

    if not vector_pool and not lexical_pool:
        return []

    fused = _rrf_fuse([vector_pool, lexical_pool])
    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    out: list[dict[str, Any]] = []
    for ext_id, score in ranked[:limit]:
        item = dict(meta.get(ext_id, {}))
        item["external_id"] = int(ext_id) if ext_id.lstrip("-").isdigit() else ext_id
        item["score"] = round(float(score), 6)
        out.append(item)
    return out


def _resource_meta(r: Any) -> dict[str, Any]:
    m = {"external_id": str(r.external_id), "name": r.name, "specialization": r.specialization}
    info = (getattr(r, "information", None) or "").strip()
    if info:
        # information хранит правила записи врача — отдаём агенту (обрезаем по бюджету).
        m["information"] = info[:1500]
    return m


def _row_to_meta(r: Any) -> dict[str, Any]:
    price = r.price
    meta = {
        "name": r.name,
        "category": r.category,
        "price": str(price) if isinstance(price, Decimal) else price,
        "duration_seconds": r.duration_seconds,
        "priority": getattr(r, "priority", 0) or 0,
    }
    # description — экспертное описание услуги (sync-safe), витрина/база прайса/правило.
    desc = (getattr(r, "description", None) or "").strip()
    if desc:
        meta["description"] = desc[:800]
    return meta
