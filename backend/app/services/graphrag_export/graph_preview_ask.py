"""Ответ на вопрос по снимку графа GraphRAG (только контекст превью)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.services.graphrag_export.graphrag_preview import agent_graphrag_workspace, load_graphrag_preview_from_workspace
from app.services.tenant_llm_config import get_decrypted_api_key

logger = structlog.get_logger(__name__)


def _preview_to_context(payload: dict[str, Any], *, max_nodes: int = 120, max_edges: int = 200) -> tuple[str, int, int]:
    nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else []
    rels = payload.get("relations") if isinstance(payload.get("relations"), list) else []
    n_use = nodes[:max_nodes]
    r_use = rels[:max_edges]
    blob = {
        "nodes": n_use,
        "relations": r_use,
    }
    return json.dumps(blob, ensure_ascii=False, indent=2), len(n_use), len(r_use)


async def answer_graph_preview_question(
    *,
    db: AsyncSession,
    agent: Agent,
    settings: Any,
    tenant_id: UUID,
    question: str,
) -> dict[str, Any]:
    ws = agent_graphrag_workspace(settings, tenant_id=tenant_id, agent=agent)
    if ws is None or not ws.is_dir():
        return {
            "answer": "Нет локального workspace GraphRAG для этого агента — сначала настройте MICROSOFT_GRAPHRAG_WORKSPACE_ROOT и пересоберите граф.",
            "used_nodes": 0,
            "used_relations": 0,
        }

    payload = load_graphrag_preview_from_workspace(ws)
    nodes = payload.get("nodes") or []
    if not nodes:
        msg = payload.get("preview_error") or payload.get("message") or "В превью нет узлов — выполните индексацию."
        return {"answer": str(msg), "used_nodes": 0, "used_relations": 0}

    ctx, used_n, used_r = _preview_to_context(payload)
    api_key = await get_decrypted_api_key(db, tenant_id, "openai")
    if not api_key:
        return {
            "answer": "Не настроен API-ключ OpenAI для организации — добавьте его в настройках LLM.",
            "used_nodes": used_n,
            "used_relations": used_r,
        }

    model = getattr(settings, "pydanticai_default_model", None) or "gpt-4o-mini"
    if isinstance(model, str) and model.startswith("openai:"):
        model = model.split(":", 1)[1]

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        sys_msg = (
            "Ты отвечаешь только на основе переданного JSON с узлами и связями графа знаний. "
            "Если данных недостаточно — так и скажи. Не выдумывай факты вне JSON."
        )
        user_msg = f"Контекст графа (JSON):\n{ctx}\n\nВопрос пользователя:\n{question.strip()}"

        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=1200,
        )
        choice = resp.choices[0].message.content if resp.choices else ""
        return {"answer": (choice or "").strip() or "Пустой ответ модели.", "used_nodes": used_n, "used_relations": used_r}
    except Exception as exc:  # noqa: BLE001
        logger.warning("graph_preview_ask_failed", error=str(exc), agent_id=str(agent.id))
        return {
            "answer": f"Не удалось получить ответ модели: {exc}",
            "used_nodes": used_n,
            "used_relations": used_r,
        }
