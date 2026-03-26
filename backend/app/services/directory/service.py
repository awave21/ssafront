"""
Сервис для работы со справочниками (Directories).

Включает:
- Поиск по справочникам (exact, fuzzy, semantic)
- Создание embeddings для семантического поиска
- Генерация tools из справочников для runtime агента
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.directory import Directory, DirectoryItem
from app.services.tenant_balance import apply_embedding_balance_charge
from app.services.tenant_llm_config import get_decrypted_api_key
from app.schemas.directory import (
    CATALOG_DIRECTORY_TEMPLATES,
    DirectorySearchResultItem,
    ResponseMode,
    SearchType,
)

if TYPE_CHECKING:
    from pydantic_ai import RunContext
    from app.services.runtime.deps import AgentDeps

logger = structlog.get_logger(__name__)


# === Lightweight rerank ===

def _text_overlap_score(query: str, text: str) -> float:
    """
    Быстрая лексическая оценка без API-вызовов.

    Алгоритм:
    1. Точное вхождение запроса в текст — score 1.0.
    2. Токенное перекрытие (Jaccard по словам).
    3. Доля слов запроса, найденных в тексте (частичный match).

    Итоговый score = max(jaccard, partial * 0.85).
    """
    if not query or not text:
        return 0.0
    q = query.lower().strip()
    t = text.lower()
    if q in t:
        return 1.0
    q_tokens = {w for w in q.split() if len(w) > 1}
    t_tokens = set(t.split())
    if not q_tokens:
        return 0.0
    overlap = len(q_tokens & t_tokens)
    union = len(q_tokens | t_tokens)
    jaccard = overlap / union if union else 0.0
    partial = sum(1 for w in q_tokens if w in t) / len(q_tokens)
    return max(jaccard, partial * 0.85)


def rerank_results(
    query: str,
    results: list[DirectorySearchResultItem],
    searchable_cols: list[str],
    *,
    vector_weight: float = 0.65,
    top_n: int | None = None,
) -> list[DirectorySearchResultItem]:
    """
    Гибридный rerank: комбинирует векторный score с лексическим.

    Не требует дополнительных API-вызовов; работает на уже полученных кандидатах.
    Применяется после _search_semantic для улучшения ранжирования при большом N кандидатов.
    """
    text_weight = 1.0 - vector_weight
    scored: list[tuple[float, DirectorySearchResultItem]] = []
    for item in results:
        item_text = " ".join(str(item.data.get(col, "")) for col in searchable_cols)
        text_score = _text_overlap_score(query, item_text)
        combined = vector_weight * item.relevance + text_weight * text_score
        scored.append((combined, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    reranked = [
        DirectorySearchResultItem(id=item.id, data=item.data, relevance=score)
        for score, item in scored
    ]
    return reranked[:top_n] if top_n else reranked


# === Поиск ===


async def search_directory_items(
    db: AsyncSession,
    directory: Directory,
    query: str,
    limit: int = 5,
    *,
    openai_api_key: str | None = None,
    rerank: bool | None = None,
    rerank_vector_weight: float | None = None,
    rerank_candidates_multiplier: int | None = None,
) -> list[DirectorySearchResultItem]:
    """
    Поиск по справочнику.

    Использует search_type справочника для выбора алгоритма:
    - exact: точное совпадение через ILIKE
    - fuzzy: нечёткий поиск через pg_trgm (similarity)
    - semantic: семантический поиск через pgvector + опциональный гибридный rerank

    rerank (bool | None): None = читать из настроек платформы (DIRECTORY_RERANK_ENABLED).
    rerank_vector_weight: вес векторного score (0–1). None = из настроек.
    rerank_candidates_multiplier: сколько кандидатов взять до rerank. None = из настроек.
    """
    from app.core.config import get_settings

    settings = get_settings()
    search_type = directory.search_type
    searchable_cols = [col["name"] for col in directory.columns if col.get("searchable")]

    if not searchable_cols:
        logger.warning(
            "no_searchable_columns",
            directory_id=str(directory.id),
        )
        return []

    if search_type == "exact":
        return await _search_exact(db, directory.id, directory.tenant_id, query, searchable_cols, limit)
    elif search_type == "fuzzy":
        return await _search_fuzzy(db, directory.id, directory.tenant_id, query, searchable_cols, limit)
    elif search_type == "semantic":
        do_rerank = rerank if rerank is not None else settings.directory_rerank_enabled
        vw = rerank_vector_weight if rerank_vector_weight is not None else settings.directory_rerank_vector_weight
        mult = rerank_candidates_multiplier if rerank_candidates_multiplier is not None else settings.directory_rerank_candidates_multiplier
        # Берём больше кандидатов для rerank, потом обрезаем до limit
        fetch_limit = limit * mult if do_rerank else limit
        results = await _search_semantic(
            db,
            directory.id,
            directory.tenant_id,
            query,
            fetch_limit,
            openai_api_key=openai_api_key,
        )
        if do_rerank and len(results) > 1:
            results = rerank_results(query, results, searchable_cols, vector_weight=vw, top_n=limit)
            logger.debug(
                "directory_rerank_applied",
                directory_id=str(directory.id),
                candidates=len(results),
                limit=limit,
            )
        return results[:limit]
    else:
        logger.error("unknown_search_type", search_type=search_type)
        return []


async def _search_exact(
    db: AsyncSession,
    directory_id: UUID,
    tenant_id: UUID,
    query: str,
    searchable_cols: list[str],
    limit: int,
) -> list[DirectorySearchResultItem]:
    """Точный поиск через ILIKE."""
    conditions = " OR ".join(f"data->>'{col}' ILIKE :query" for col in searchable_cols)
    
    sql = text(f"""
        SELECT id, data, 1.0 as relevance
        FROM directory_items
        WHERE directory_id = :directory_id
          AND tenant_id = :tenant_id
          AND ({conditions})
        ORDER BY created_at DESC
        LIMIT :limit
    """)
    
    result = await db.execute(
        sql,
        {
            "directory_id": directory_id,
            "tenant_id": tenant_id,
            "query": f"%{query}%",
            "limit": limit,
        },
    )
    
    return [
        DirectorySearchResultItem(
            id=row.id,
            data=row.data,
            relevance=row.relevance,
        )
        for row in result.fetchall()
    ]


async def _search_fuzzy(
    db: AsyncSession,
    directory_id: UUID,
    tenant_id: UUID,
    query: str,
    searchable_cols: list[str],
    limit: int,
) -> list[DirectorySearchResultItem]:
    """Нечёткий поиск через pg_trgm similarity."""
    # Создаём условия для каждой searchable колонки
    similarity_exprs = [f"similarity(COALESCE(data->>'{col}', ''), :query)" for col in searchable_cols]
    max_similarity = f"GREATEST({', '.join(similarity_exprs)})"
    
    # Условия фильтрации (similarity > 0.3)
    filter_conditions = " OR ".join(f"similarity(COALESCE(data->>'{col}', ''), :query) > 0.2" for col in searchable_cols)
    
    sql = text(f"""
        SELECT id, data, {max_similarity} as relevance
        FROM directory_items
        WHERE directory_id = :directory_id
          AND tenant_id = :tenant_id
          AND ({filter_conditions})
        ORDER BY relevance DESC
        LIMIT :limit
    """)
    
    result = await db.execute(
        sql,
        {
            "directory_id": directory_id,
            "tenant_id": tenant_id,
            "query": query,
            "limit": limit,
        },
    )
    
    return [
        DirectorySearchResultItem(
            id=row.id,
            data=row.data,
            relevance=float(row.relevance),
        )
        for row in result.fetchall()
    ]


async def _search_semantic(
    db: AsyncSession,
    directory_id: UUID,
    tenant_id: UUID,
    query: str,
    limit: int,
    *,
    openai_api_key: str | None = None,
) -> list[DirectorySearchResultItem]:
    """Семантический поиск через pgvector."""
    # Используем ключ из AgentDeps (если передан) — экономим DB-запрос в runtime.
    # Фолбек на DB-запрос сохраняем для вызовов вне контекста агента (тесты, API).
    if not openai_api_key:
        openai_api_key = await get_decrypted_api_key(db, tenant_id)
    if not openai_api_key:
        logger.warning("semantic_search_skipped_missing_tenant_llm_key", tenant_id=str(tenant_id))
        return []

    # Создаём embedding для запроса
    query_embedding = await create_embedding(
        query,
        openai_api_key=openai_api_key,
        db=db,
        tenant_id=tenant_id,
        charge_source_type="embedding.directory_query",
        charge_metadata={"directory_id": str(directory_id)},
    )
    
    if query_embedding is None:
        logger.warning("failed_to_create_query_embedding")
        return []
    
    # Форматируем embedding для PostgreSQL
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    
    sql = text("""
        SELECT id, data, 1 - (embedding <=> CAST(:embedding AS vector)) as relevance
        FROM directory_items
        WHERE directory_id = :directory_id
          AND tenant_id = :tenant_id
          AND embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)
    
    result = await db.execute(
        sql,
        {
            "directory_id": directory_id,
            "tenant_id": tenant_id,
            "embedding": embedding_str,
            "limit": limit,
        },
    )
    
    return [
        DirectorySearchResultItem(
            id=row.id,
            data=row.data,
            relevance=float(row.relevance) if row.relevance else 0.0,
        )
        for row in result.fetchall()
    ]


# === Embeddings ===


async def create_embedding(
    text: str,
    *,
    openai_api_key: str | None = None,
    db: AsyncSession | None = None,
    tenant_id: UUID | None = None,
    charge_source_type: str | None = None,
    charge_source_id: str | None = None,
    charge_metadata: dict[str, Any] | None = None,
) -> list[float] | None:
    """
    Создаёт embedding через OpenAI API.

    Модель берётся из настроек платформы (EMBEDDING_MODEL, по умолчанию text-embedding-3-small).
    Размерность вектора должна соответствовать схеме БД.
    """
    if not openai_api_key:
        logger.warning("embedding_skipped_missing_tenant_llm_key")
        return None

    try:
        from app.core.config import get_settings
        from app.services.runtime.model_resolver import resolve_openai_client

        settings = get_settings()
        client = resolve_openai_client(openai_api_key=openai_api_key)
        response = await client.embeddings.create(
            input=text,
            model=settings.embedding_model,
        )
        embedding = response.data[0].embedding
        if db is not None and tenant_id is not None and charge_source_type:
            usage = getattr(response, "usage", None)
            total_tokens = getattr(usage, "total_tokens", None)
            if total_tokens is None:
                total_tokens = getattr(usage, "prompt_tokens", None)
            if isinstance(total_tokens, int) and total_tokens > 0:
                metadata = {
                    "model": settings.embedding_model,
                    "input_tokens": total_tokens,
                    **(charge_metadata or {}),
                }
                try:
                    await apply_embedding_balance_charge(
                        db,
                        tenant_id=tenant_id,
                        model_name=settings.embedding_model,
                        input_tokens=total_tokens,
                        source_type=charge_source_type,
                        source_id=charge_source_id or str(uuid4()),
                        metadata=metadata,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("embedding_balance_charge_failed", error=str(exc))
        return embedding
    except Exception as e:
        logger.error("embedding_creation_failed", error=str(e))
        return None


async def update_item_embedding(
    db: AsyncSession,
    item: DirectoryItem,
    directory: Directory,
) -> None:
    """
    Обновляет embedding для записи справочника.
    
    Собирает текст из searchable полей и создаёт embedding.
    """
    if directory.search_type != "semantic":
        return
    
    searchable_cols = [col["name"] for col in directory.columns if col.get("searchable")]
    if not searchable_cols:
        return
    
    # Собираем текст из searchable полей
    text_parts = [str(item.data.get(col, "")) for col in searchable_cols]
    combined_text = " ".join(filter(None, text_parts))
    
    if not combined_text.strip():
        return

    openai_api_key = await get_decrypted_api_key(db, directory.tenant_id)
    if not openai_api_key:
        logger.warning(
            "embedding_update_skipped_missing_tenant_llm_key",
            tenant_id=str(directory.tenant_id),
            directory_id=str(directory.id),
            item_id=str(item.id),
        )
        return

    embedding = await create_embedding(
        combined_text,
        openai_api_key=openai_api_key,
        db=db,
        tenant_id=directory.tenant_id,
        charge_source_type="embedding.directory_item",
        charge_source_id=str(item.id),
        charge_metadata={"directory_id": str(directory.id), "item_id": str(item.id)},
    )
    if embedding:
        # Используем raw SQL для надёжного сохранения вектора
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        await db.execute(
            text("UPDATE directory_items SET embedding = CAST(:embedding AS vector) WHERE id = :id"),
            {"embedding": embedding_str, "id": item.id},
        )
        await db.commit()
        logger.info("embedding_saved", item_id=str(item.id))


async def update_directory_embeddings(
    db: AsyncSession,
    directory: Directory,
) -> int:
    """
    Обновляет embeddings для записей без embedding.
    
    Возвращает количество обновлённых записей.
    """
    if directory.search_type != "semantic":
        return 0
    
    from sqlalchemy import select
    
    # Выбираем только записи БЕЗ embedding
    stmt = select(DirectoryItem).where(
        DirectoryItem.directory_id == directory.id,
        DirectoryItem.embedding.is_(None),
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    
    if not items:
        return 0
    
    updated = 0
    for item in items:
        await update_item_embedding(db, item, directory)
        updated += 1
    
    logger.info(
        "embeddings_updated",
        directory_id=str(directory.id),
        count=updated,
    )
    
    return updated


# === Tool Generation ===


def format_search_results(
    results: list[DirectorySearchResultItem],
    directory: Directory,
) -> dict[str, Any]:
    """
    Форматирует результаты поиска для ответа.
    
    response_mode определяет формат:
    - function_result: подробный формат для агента
    - direct_message: краткий формат для пользователя
    """
    if not results:
        return {
            "status": "no_match",
            "mode": directory.response_mode,
            "message": "Ничего не найдено.",
            "items": [],
        }

    if directory.response_mode == "direct_message":
        # For Q/A template pass exact answer as end-user message.
        if directory.template == "qa":
            top_item = results[0]
            exact_message = str(top_item.data.get("answer") or "").strip()
            if exact_message:
                return {
                    "status": "ok",
                    "mode": "direct_message",
                    "message": exact_message,
                    "exact_user_message": exact_message,
                    "items": [{"id": str(top_item.id), "data": top_item.data}],
                }
        lines: list[str] = []
        for item in results:
            parts: list[str] = []
            for col in directory.columns:
                col_name = col["name"]
                value = item.data.get(col_name)
                if value is not None:
                    parts.append(str(value))
            if parts:
                lines.append(" — ".join(parts))
        final_message = "\n".join(lines).strip() or "Ничего не найдено."
        return {
            "status": "ok",
            "mode": "direct_message",
            "message": final_message,
            "exact_user_message": final_message,
            "items": [{"id": str(item.id), "data": item.data} for item in results],
        }

    return {
        "status": "ok",
        "mode": "function_result",
        "message": f"Найдено {len(results)} результатов",
        "total": len(results),
        "items": [{"id": str(item.id), "data": item.data, "relevance": item.relevance} for item in results],
    }


def create_directory_tool(
    directory: Directory,
    db_session_factory: Callable[[], AsyncSession],
) -> dict[str, Any]:
    """
    Создаёт tool из справочника для pydantic-ai агента.
    
    Возвращает словарь с информацией о tool'е:
    - name: имя функции
    - description: описание
    - function: async функция для вызова
    """
    async def tool_fn(ctx: "RunContext[AgentDeps]", query: str = "") -> dict[str, Any]:
        """Поиск по справочнику."""
        # Читаем ключ из deps — единый DB-запрос на весь запуск агента.
        deps: "AgentDeps | None" = getattr(ctx, "deps", None)
        injected_key: str | None = deps.openai_api_key if deps is not None else None

        async with db_session_factory() as db:
            # Перезагружаем directory в текущей сессии
            from sqlalchemy import select
            stmt = select(Directory).where(Directory.id == directory.id)
            dir_result = await db.execute(stmt)
            current_directory = dir_result.scalar_one_or_none()

            if current_directory is None or not current_directory.is_enabled:
                return {
                    "status": "error",
                    "mode": "direct_message",
                    "message": "Справочник недоступен.",
                    "items": [],
                }

            results = await search_directory_items(
                db=db,
                directory=current_directory,
                query=query,
                limit=5,
                openai_api_key=injected_key,
            )
            
            return format_search_results(results, current_directory)
    
    # Устанавливаем имя и docstring
    tool_fn.__name__ = directory.tool_name
    tool_fn.__doc__ = directory.tool_description or f"Поиск по справочнику '{directory.name}'"
    
    return {
        "name": directory.tool_name,
        "description": directory.tool_description or f"Поиск по справочнику '{directory.name}'",
        "function": tool_fn,
    }


async def get_agent_directory_tools(
    db: AsyncSession,
    agent_id: UUID,
    db_session_factory: Callable[[], AsyncSession],
    *,
    only_catalog_templates: bool = False,
) -> list[dict[str, Any]]:
    """
    Получает все tools из справочников агента.

    only_catalog_templates=True — только шаблоны из CATALOG_DIRECTORY_TEMPLATES
    (qa, service_catalog, theme_catalog, …), без произвольного custom.
    """
    from sqlalchemy import select

    stmt = select(Directory).where(
        Directory.agent_id == agent_id,
        Directory.is_deleted.is_(False),
        Directory.is_enabled.is_(True),
        Directory.items_count > 0,
    )
    if only_catalog_templates:
        stmt = stmt.where(Directory.template.in_(tuple(CATALOG_DIRECTORY_TEMPLATES)))
    result = await db.execute(stmt)
    directories = result.scalars().all()
    
    tools: list[dict[str, Any]] = []
    for directory in directories:
        tool = create_directory_tool(directory, db_session_factory)
        tools.append(tool)
    
    logger.info(
        "directory_tools_loaded",
        agent_id=str(agent_id),
        count=len(tools),
    )
    
    return tools
