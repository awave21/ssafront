"""Ответ на вопрос по графу GraphRAG с переключением режимов поиска.

Поддерживаемые режимы:
- ``naive``  — fallback: первые N узлов превью + LLM (быстрый, без эмбеддингов).
- ``basic``  — стандартный векторный поиск по text_units (Microsoft GraphRAG CLI).
- ``local``  — entity-centric поиск (entities + relationships + text_units).
- ``global`` — map-reduce по community reports.
- ``drift``  — local + community context, рекомендуемый дефолт.

Для всех режимов кроме ``naive`` запускается ``graphrag query --method <m>``
в каталоге workspace агента. Возвращаются также system-prompt шаблон и
полная команда — чтобы видеть, что именно ушло в LLM.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.services.graphrag_export.graphrag_preview import (
    agent_graphrag_workspace,
    load_graphrag_preview_from_workspace,
)
from app.services.graphrag_export.graphrag_query_cli import run_graphrag_query
from app.services.tenant_llm_config import get_decrypted_api_key

logger = structlog.get_logger(__name__)

GraphSearchMethod = Literal["naive", "basic", "local", "global", "drift"]
SUPPORTED_METHODS: tuple[GraphSearchMethod, ...] = ("naive", "basic", "local", "global", "drift")

_PROMPT_FILES: dict[GraphSearchMethod, tuple[str, ...]] = {
    "basic": ("basic_search_system_prompt.txt",),
    "local": ("local_search_system_prompt.txt",),
    "global": (
        "global_search_map_system_prompt.txt",
        "global_search_reduce_system_prompt.txt",
        "global_search_knowledge_system_prompt.txt",
    ),
    "drift": ("drift_search_system_prompt.txt", "drift_reduce_prompt.txt"),
    "naive": (),
}


def _read_prompt_templates(ws: Path, method: GraphSearchMethod) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for name in _PROMPT_FILES.get(method, ()):
        p = ws / "prompts" / name
        if not p.is_file():
            continue
        try:
            out.append({"name": name, "content": p.read_text(encoding="utf-8")})
        except OSError:
            continue
    return out


def _preview_to_naive_context(payload: dict[str, Any]) -> tuple[str, int, int]:
    """Сериализует ВСЕ узлы/связи, которые вернул preview-loader.

    Лимит на размер уже зашит в loader (``_MAX_NODES`` / ``_MAX_EDGES``) и привязан
    к токен-бюджету модели. Дополнительно резать здесь не нужно.
    """
    nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else []
    rels = payload.get("relations") if isinstance(payload.get("relations"), list) else []
    return json.dumps({"nodes": nodes, "relations": rels}, ensure_ascii=False, indent=2), len(nodes), len(rels)


async def _run_naive(
    *,
    db: AsyncSession,
    agent: Agent,
    settings: Any,
    tenant_id: UUID,
    ws: Path,
    question: str,
) -> dict[str, Any]:
    payload = load_graphrag_preview_from_workspace(ws)
    nodes = payload.get("nodes") or []
    if not nodes:
        msg = payload.get("preview_error") or payload.get("message") or "В превью нет узлов — выполните индексацию."
        return {"answer": str(msg), "used_nodes": 0, "used_relations": 0, "user_prompt": question}

    total_nodes = int(payload.get("node_count") or len(nodes))
    total_edges = int(payload.get("edge_count") or len(payload.get("relations") or []))
    ctx, used_n, used_r = _preview_to_naive_context(payload)
    api_key = await get_decrypted_api_key(db, tenant_id, "openai")
    if not api_key:
        return {
            "answer": "Не настроен API-ключ OpenAI для организации — добавьте его в настройках LLM.",
            "used_nodes": used_n,
            "used_relations": used_r,
            "total_nodes": total_nodes,
            "total_relations": total_edges,
            "user_prompt": question,
        }

    model = getattr(settings, "pydanticai_default_model", None) or "gpt-4o-mini"
    if isinstance(model, str) and model.startswith("openai:"):
        model = model.split(":", 1)[1]

    sys_msg = (
        "Ты отвечаешь только на основе переданного JSON с узлами и связями графа знаний. "
        "Если данных недостаточно — так и скажи. Не выдумывай факты вне JSON. "
        "Всегда используй человекочитаемые названия сущностей (name/title/label). "
        "Не описывай сущности через UUID, external_id, numeric id или шаблоны вида "
        "'Специалист 1'/'Услуга 3'/'Категория 2', если в JSON есть более точное имя."
    )
    user_msg = f"Контекст графа (JSON):\n{ctx}\n\nВопрос пользователя:\n{question.strip()}"

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            temperature=0.2,
            max_tokens=1200,
        )
        choice = resp.choices[0].message.content if resp.choices else ""
        return {
            "answer": (choice or "").strip() or "Пустой ответ модели.",
            "used_nodes": used_n,
            "used_relations": used_r,
            "total_nodes": total_nodes,
            "total_relations": total_edges,
            "system_prompt": sys_msg,
            "user_prompt": user_msg,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("graph_preview_ask_naive_failed", error=str(exc), agent_id=str(agent.id))
        return {
            "answer": f"Не удалось получить ответ модели: {exc}",
            "used_nodes": used_n,
            "used_relations": used_r,
            "total_nodes": total_nodes,
            "total_relations": total_edges,
            "system_prompt": sys_msg,
            "user_prompt": user_msg,
        }


async def _run_graphrag_cli(
    *,
    db: AsyncSession,
    agent: Agent,
    settings: Any,
    tenant_id: UUID,
    ws: Path,
    question: str,
    method: GraphSearchMethod,
    timeout_sec: float = 180.0,
) -> dict[str, Any]:
    if method == "naive":
        return {"answer": "naive не должен попадать в CLI-путь.", "used_nodes": 0, "used_relations": 0}
    res = await run_graphrag_query(
        db=db, settings=settings, tenant_id=tenant_id, ws=ws,
        question=question, method=method, timeout_sec=timeout_sec,  # type: ignore[arg-type]
    )
    if not res.get("ok"):
        if res.get("error") == "no_api_key":
            answer = "Не настроен API-ключ OpenAI для организации — добавьте его в настройках LLM."
        elif res.get("error") == "no_cli":
            answer = "В контейнере нет CLI graphrag. Установите пакет graphrag или задайте MICROSOFT_GRAPHRAG_CLI."
        elif res.get("error") == "timeout":
            answer = f"Превышен таймаут запроса graphrag ({int(timeout_sec)} с) для метода {method}."
        else:
            tail = res.get("stderr_tail") or ""
            answer = f"Метод {method} завершился ошибкой (exit={res.get('exit_code')}):\n{tail[:1500]}"
        return {
            "answer": answer,
            "used_nodes": 0,
            "used_relations": 0,
            "command": res.get("command"),
            "latency_ms": res.get("latency_ms"),
        }

    return {
        "answer": res.get("answer") or "Пустой ответ модели.",
        "used_nodes": 0,
        "used_relations": 0,
        "command": res.get("command"),
        "latency_ms": res.get("latency_ms"),
        "stderr_tail": res.get("stderr_tail") or "",
    }


async def answer_graph_preview_question(
    *,
    db: AsyncSession,
    agent: Agent,
    settings: Any,
    tenant_id: UUID,
    question: str,
    method: GraphSearchMethod = "naive",
) -> dict[str, Any]:
    if method not in SUPPORTED_METHODS:
        method = "naive"

    ws = agent_graphrag_workspace(settings, tenant_id=tenant_id, agent=agent)
    if ws is None or not ws.is_dir():
        return {
            "answer": "Нет локального workspace GraphRAG для этого агента — настройте MICROSOFT_GRAPHRAG_WORKSPACE_ROOT и пересоберите граф.",
            "used_nodes": 0,
            "used_relations": 0,
            "method": method,
            "prompt_templates": [],
            "user_prompt": question,
        }

    if method == "naive":
        result = await _run_naive(
            db=db, agent=agent, settings=settings, tenant_id=tenant_id, ws=ws, question=question,
        )
    else:
        result = await _run_graphrag_cli(
            db=db, agent=agent, settings=settings, tenant_id=tenant_id, ws=ws, question=question, method=method,
        )

    result.setdefault("user_prompt", question)
    result["method"] = method
    result["prompt_templates"] = _read_prompt_templates(ws, method)
    return result
