"""Запуск ``graphrag query --method <m>`` через subprocess.

Используется как виджетом «Вопрос к графу», так и рантайм-тулом агента.
Возвращает чистый markdown-ответ модели, без декоративных рамок CLI.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.graphrag_export.local_index import _graphrag_argv_prefix, _run_graphrag_subprocess
from app.services.tenant_llm_config import get_decrypted_api_key

logger = structlog.get_logger(__name__)

GraphragQueryMethod = Literal["basic", "local", "global", "drift"]


def strip_cli_decorations(text: str) -> str:
    """GraphRAG CLI оборачивает финальный ответ в маркер ``SUCCESS: ... Search Response:``."""
    if not text:
        return ""
    markers = (
        "SUCCESS: Local Search Response:",
        "SUCCESS: Global Search Response:",
        "SUCCESS: DRIFT Search Response:",
        "SUCCESS: Basic Search Response:",
    )
    for m in markers:
        idx = text.rfind(m)
        if idx >= 0:
            return text[idx + len(m):].strip()
    return text.strip()


async def run_graphrag_query(
    *,
    db: AsyncSession,
    settings: Any,
    tenant_id: UUID,
    ws: Path,
    question: str,
    method: GraphragQueryMethod,
    timeout_sec: float = 120.0,
) -> dict[str, Any]:
    """Запускает ``graphrag query`` и возвращает ``{ok, answer, source, command, latency_ms, stderr_tail}``.

    На любой ошибке возвращает ``ok=False`` с заполненным ``error``.
    """
    api_key = await get_decrypted_api_key(db, tenant_id, "openai")
    if not api_key:
        return {"ok": False, "error": "no_api_key", "source": "graphrag_no_api_key"}

    prefix = _graphrag_argv_prefix(settings)
    if not prefix:
        return {"ok": False, "error": "no_cli", "source": "graphrag_no_cli"}

    args = [*prefix, "query", "--root", ".", "--method", method, question.strip()]
    env = {**os.environ, "OPENAI_API_KEY": api_key, "GRAPHRAG_API_KEY": api_key}
    cmd_string = " ".join(args)

    started = time.monotonic()
    try:
        code, out, err = await _run_graphrag_subprocess(ws, args, env, timeout_sec=timeout_sec)
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "error": "timeout",
            "source": f"graphrag_timeout_{method}",
            "command": cmd_string,
            "latency_ms": int((time.monotonic() - started) * 1000),
        }

    latency_ms = int((time.monotonic() - started) * 1000)
    if code != 0:
        logger.warning(
            "graphrag_query_cli_failed",
            method=method,
            code=code,
            stderr=err[:1500],
        )
        return {
            "ok": False,
            "error": "exit_code",
            "exit_code": code,
            "source": f"graphrag_error_{method}",
            "command": cmd_string,
            "latency_ms": latency_ms,
            "stderr_tail": err[-1500:] if err else "",
        }

    answer = strip_cli_decorations(out)
    return {
        "ok": True,
        "answer": answer or "",
        "source": f"graphrag_{method}",
        "command": cmd_string,
        "latency_ms": latency_ms,
        "stderr_tail": err[-1500:] if err else "",
    }
