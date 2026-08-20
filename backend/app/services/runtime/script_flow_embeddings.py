"""Заливка эмбеддингов узлов script flow в Postgres (`script_flow_node_indexes.embedding`).

pgvector-путь тактик: узлы эксперта эмбедятся тем же обогащённым текстом, что и
графовый синк (`script_flow_canvas_neo4j_sync._build_enriched_text`), но вектор
пишется в колонку Postgres — чтобы `search_expert_tactics` работал семантически
без Neo4j.

Строки `script_flow_node_indexes` полностью пересоздаются при каждой переиндексации
потока (`_index_flow`: delete+insert), поэтому хеш-гейт не нужен — эмбеддинги
считаются один раз на переиндексацию.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.script_flow_node_index import ScriptFlowNodeIndex
from app.services.directory.service import create_embeddings_batch

logger = structlog.get_logger(__name__)


def build_script_flow_embed_text(node: ScriptFlowNodeIndex, *, flow_name: str | None = None) -> str:
    """Обогащённый текст ноды для эмбеддинга.

    Намеренно НЕ включаем имя потока: замеры показали, что префикс «Поток: …»
    размывает короткие реплики-возражения («подумаю»/«дорого») и роняет их близость
    ниже порога, при этом маршрутизацию по услуге вытягивает сам контент ноды.
    `flow_name` оставлен в сигнатуре для совместимости вызовов и возможного A/B.
    """
    parts: list[str] = []
    if node.stage:
        parts.append(f"Этап: {node.stage}")
    if node.node_type:
        parts.append(f"Тип ноды: {node.node_type}")
    if node.title:
        parts.append(f"Тема: {node.title}")
    if node.content_text:
        parts.append(node.content_text)
    return "\n".join(parts).strip()


async def embed_script_flow_nodes(
    *,
    db: AsyncSession,
    nodes: list[ScriptFlowNodeIndex],
    openai_api_key: str | None,
    tenant_id: UUID | None = None,
    flow_name: str | None = None,
) -> int:
    """Посчитать и записать эмбеддинги в `script_flow_node_indexes.embedding`.

    Возвращает количество успешно записанных векторов. Пустые/несёрчабельные
    ноды пропускаются. Ошибка на конкретный батч → соответствующие ноды остаются
    без эмбеддинга (fallback ретривера — лексика).
    """
    if not openai_api_key or not nodes:
        return 0

    targets = [n for n in nodes if getattr(n, "is_searchable", True)]
    texts = [build_script_flow_embed_text(n, flow_name=flow_name) for n in targets]
    pairs = [(n, t) for n, t in zip(targets, texts) if t]
    if not pairs:
        return 0

    embeddings = await create_embeddings_batch(
        [t for _n, t in pairs],
        openai_api_key=openai_api_key,
        db=db,
        tenant_id=tenant_id,
        charge_source_type="embedding.script_flow_node",
    )

    written = 0
    for (node, _t), emb in zip(pairs, embeddings):
        if not emb:
            continue
        # asyncpg-готча: биндим вектор как text-литерал + двойной CAST, не list[float].
        emb_str = "[" + ",".join(str(float(x)) for x in emb) + "]"
        await db.execute(
            text(
                "UPDATE script_flow_node_indexes "
                "SET embedding = CAST(CAST(:emb AS text) AS vector) "
                "WHERE id = :id"
            ),
            {"emb": emb_str, "id": node.id},
        )
        written += 1

    await db.commit()
    logger.info(
        "script_flow_nodes_embedded",
        nodes=len(pairs),
        written=written,
        flow_name=flow_name,
    )
    return written
