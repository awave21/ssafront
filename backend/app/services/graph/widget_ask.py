"""Виджет «Спросить у графа» — режим prod: query_graphrag + system_prompt агента."""
from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

ADMIN_SYSTEM_PROMPT = """Ты — администратор премиум-клиники косметологии. Отвечаешь пациенту-клиенту.

ПРАВИЛА:
1. Используй ТОЛЬКО факты из JSON ниже («контекст графа»). Если данных не хватает — \
честно скажи: «В нашей базе нет данных по вашему вопросу, передам менеджеру».
2. Не выдумывай услуги, специалистов, цены, противопоказания.
3. Имена и названия — точно как в JSON. Не «врач косметолог», а «Иванова М.П.».
4. При обсуждении услуги указывай связанных специалистов, если есть в JSON.
5. Стиль — профессиональный, доброжелательный, на «вы»."""


async def widget_ask(
    *,
    db: AsyncSession,
    agent: Any,
    tenant_id: UUID,
    question: str,
    top_k: int = 5,
) -> dict[str, Any]:
    """Спросить у графа в режиме prod: query_graphrag + system_prompt агента."""
    from openai import AsyncOpenAI

    from app.core.config import get_settings
    from app.services.runtime.graphrag_tool import query_graphrag
    from app.services.tenant_llm_config import get_decrypted_api_key

    started = time.perf_counter()

    system_prompt = (getattr(agent, "system_prompt", None) or "").strip() or ADMIN_SYSTEM_PROMPT

    api_key = await get_decrypted_api_key(db, tenant_id)
    if not api_key:
        return {
            "answer": "Не настроен API-ключ OpenAI для тенанта — поиск по графу недоступен.",
            "retrieval_path": "neo4j_hybrid",
            "retrieved_nodes": [],
            "service_candidates": [],
            "specialist_candidates": [],
            "category_candidates": [],
            "system_prompt": system_prompt,
            "user_prompt": "",
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "tokens": {"in": 0, "out": 0},
        }

    settings = get_settings()

    try:
        graphrag_result = await query_graphrag(
            db,
            settings=settings,
            agent=agent,
            tenant_id=tenant_id,
            query=question,
            focus="auto",
            max_candidates=top_k,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("widget_ask_graphrag_failed", agent_id=str(agent.id), error=str(exc))
        return {
            "answer": "Neo4j недоступен — поиск по графу недоступен.",
            "retrieval_path": "neo4j_hybrid",
            "retrieved_nodes": [],
            "service_candidates": [],
            "specialist_candidates": [],
            "category_candidates": [],
            "system_prompt": system_prompt,
            "user_prompt": "",
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "tokens": {"in": 0, "out": 0},
        }

    tool_result_json = json.dumps(graphrag_result, ensure_ascii=False, indent=2)
    user_prompt = (
        f"Результат инструмента query_graphrag (JSON):\n{tool_result_json}"
        f"\n\nВопрос клиента:\n{question.strip()}"
    )

    client = AsyncOpenAI(api_key=api_key)
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    answer = (resp.choices[0].message.content or "").strip()
    in_tokens = resp.usage.prompt_tokens if resp.usage else 0
    out_tokens = resp.usage.completion_tokens if resp.usage else 0

    return {
        "answer": answer,
        "retrieval_path": graphrag_result.get("retrieval_path", "neo4j_hybrid"),
        "retrieved_nodes": graphrag_result.get("script_context", []),
        "service_candidates": graphrag_result.get("service_candidates", []),
        "specialist_candidates": graphrag_result.get("specialist_candidates", []),
        "category_candidates": graphrag_result.get("category_candidates", []),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "tokens": {"in": in_tokens, "out": out_tokens},
    }
