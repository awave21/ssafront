"""Эмбеддинги для узлов unified-графа.

Используем уже существующую колонку ``agent_unified_graph_nodes.embedding`` (Vector 1536)
и тот же embedding-сервис, что и для direct_questions / directory_items.

Идея: эмбеддинг = title + первая часть description. Хеш контента (sha256) хранится
в ``embedding_content_hash`` — пересчитываем только при изменении.
"""
from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_unified_graph_node import AgentUnifiedGraphNode
from app.services.directory.service import create_embedding
from app.services.tenant_llm_config import get_decrypted_api_key

log = structlog.get_logger(__name__)

# Лимит, чтобы не перегружать OpenAI и не молотить эмбеддинги до бесконечности.
MAX_NODES_PER_RUN = 1000
DESCRIPTION_CHARS_FOR_EMBEDDING = 1000
EMBEDDING_CONCURRENCY = 8


@dataclass
class EmbeddingResult:
    computed: int
    skipped: int
    failed: int


def _content_for_embedding(node: AgentUnifiedGraphNode) -> str:
    """Текст, по которому считаем эмбеддинг узла."""
    parts: list[str] = []
    if node.title:
        parts.append(node.title)
    if node.description:
        parts.append(node.description[:DESCRIPTION_CHARS_FOR_EMBEDDING])
    return "\n".join(parts).strip()


def _content_hash(text: str, model_signature: str) -> str:
    """Хеш для invalidation: при изменении модели/текста — пересчёт."""
    h = hashlib.sha256()
    h.update(model_signature.encode("utf-8"))
    h.update(b"\n")
    h.update(text.encode("utf-8"))
    return h.hexdigest()[:64]


async def compute_node_embeddings(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    max_nodes: int = MAX_NODES_PER_RUN,
) -> EmbeddingResult:
    """Считает эмбеддинги для узлов, у которых их нет либо хеш контента изменился.

    Использует API-ключ OpenAI тенанта из БД. Списывает балансовый charge
    через тот же путь, что direct_questions/directory_items.
    """
    api_key = await get_decrypted_api_key(db, tenant_id, "openai")
    if not api_key:
        log.warning("unified_graph.embeddings.no_api_key", tenant_id=str(tenant_id))
        return EmbeddingResult(computed=0, skipped=0, failed=0)

    from app.core.config import get_settings
    settings = get_settings()
    model_signature = settings.embedding_model

    rows = (
        await db.execute(
            select(AgentUnifiedGraphNode).where(AgentUnifiedGraphNode.agent_id == agent_id)
        )
    ).scalars().all()

    pending: list[tuple[AgentUnifiedGraphNode, str, str]] = []
    skipped = 0
    for node in rows:
        content = _content_for_embedding(node)
        if not content:
            skipped += 1
            continue
        new_hash = _content_hash(content, model_signature)
        if node.embedding is not None and node.embedding_content_hash == new_hash:
            skipped += 1
            continue
        pending.append((node, content, new_hash))
        if len(pending) >= max_nodes:
            break

    if not pending:
        return EmbeddingResult(computed=0, skipped=skipped, failed=0)

    sem = asyncio.Semaphore(EMBEDDING_CONCURRENCY)

    async def _compute_one(node: AgentUnifiedGraphNode, content: str, h: str) -> tuple[UUID, list[float] | None, str]:
        async with sem:
            emb = await create_embedding(
                content,
                openai_api_key=api_key,
                db=db,
                tenant_id=tenant_id,
                charge_source_type="unified_graph_node",
                charge_source_id=str(node.id),
                charge_metadata={"agent_id": str(agent_id), "entity_type": node.entity_type},
            )
            return node.id, emb, h

    results = await asyncio.gather(
        *[_compute_one(n, t, h) for (n, t, h) in pending],
        return_exceptions=True,
    )

    computed = 0
    failed = 0
    for r in results:
        if isinstance(r, Exception):
            failed += 1
            continue
        node_id, emb, h = r
        if emb is None:
            failed += 1
            continue
        # Raw SQL для надёжного сохранения pgvector — asyncpg-адаптер
        # не всегда корректно сериализует list[float] в Vector.
        emb_str = "[" + ",".join(str(float(x)) for x in emb) + "]"
        await db.execute(
            text(
                "UPDATE agent_unified_graph_nodes "
                "SET embedding = CAST(CAST(:emb AS text) AS vector), "
                "    embedding_content_hash = :h "
                "WHERE id = :id"
            ),
            {"emb": emb_str, "h": h, "id": node_id},
        )
        computed += 1
    await db.commit()

    log.info(
        "unified_graph.embeddings.done",
        agent_id=str(agent_id),
        computed=computed,
        skipped=skipped,
        failed=failed,
    )
    return EmbeddingResult(computed=computed, skipped=skipped, failed=failed)
