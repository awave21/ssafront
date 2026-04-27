"""Индексация Microsoft GraphRAG: HTTP webhook или локальный ``graphrag index``."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.agent import Agent
from app.db.session import async_session_factory
from app.services.graphrag_export.local_index import run_local_microsoft_graphrag_index
from app.services.graphrag_export.sqns_corpus import build_sqns_graphrag_corpus

logger = structlog.get_logger(__name__)


async def dispatch_microsoft_graphrag_corpus(
    *,
    db: AsyncSession,
    agent: Agent,
    settings: Settings | None = None,
    active_sqns_only: bool = True,
) -> tuple[bool, str]:
    """
    Приоритет:

    1. ``MICROSOFT_GRAPHRAG_WORKSPACE_ROOT`` — локально: ``input/*.txt`` + ``graphrag init`` / ``graphrag index``.
    2. Иначе ``MICROSOFT_GRAPHRAG_INDEX_WEBHOOK_URL`` — POST multipart ``corpus`` (UTF-8 .txt).

    Локальный режим идёт первым, чтобы старый/битый webhook в ``.env`` не блокировал индексацию
    при уже настроенном каталоге workspace (например в docker-compose по умолчанию).
    """
    cfg = settings or get_settings()
    url = (cfg.microsoft_graphrag_index_webhook_url or "").strip()
    ws_root = (cfg.microsoft_graphrag_workspace_root or "").strip()

    if ws_root:
        logger.info("microsoft_graphrag_dispatch_mode", mode="local", agent_id=str(agent.id))
        return await run_local_microsoft_graphrag_index(
            db=db, agent=agent, settings=cfg, active_sqns_only=active_sqns_only
        )

    if url:
        body, filename = await build_sqns_graphrag_corpus(db, agent.id, active_sqns_only=active_sqns_only)
        headers: dict[str, str] = {}
        bearer = (cfg.microsoft_graphrag_index_webhook_bearer or "").strip()
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"

        try:
            async with httpx.AsyncClient(timeout=cfg.microsoft_graphrag_webhook_timeout_seconds) as client:
                r = await client.post(
                    url,
                    data={
                        "agent_id": str(agent.id),
                        "tenant_id": str(agent.tenant_id),
                    },
                    files={"corpus": (filename, body, "text/plain; charset=utf-8")},
                    headers=headers or None,
                )
                r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "microsoft_graphrag_webhook_http_error",
                status=exc.response.status_code,
                agent_id=str(agent.id),
            )
            return False, f"HTTP {exc.response.status_code}: {exc.response.text[:500]}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("microsoft_graphrag_webhook_failed", error=str(exc), agent_id=str(agent.id))
            return False, str(exc)

        logger.info("microsoft_graphrag_corpus_dispatched", agent_id=str(agent.id), filename=filename)
        agent.microsoft_graphrag_last_indexed_at = datetime.now(timezone.utc)
        await db.commit()
        return True, "ok"

    return False, "Нет MICROSOFT_GRAPHRAG_WORKSPACE_ROOT и нет MICROSOFT_GRAPHRAG_INDEX_WEBHOOK_URL."


async def _dispatch_with_new_session(agent_id: UUID, tenant_id: UUID) -> None:
    cfg = get_settings()
    if not cfg.microsoft_graphrag_auto_dispatch_corpus:
        return
    if not (cfg.microsoft_graphrag_index_webhook_url or "").strip() and not (
        cfg.microsoft_graphrag_workspace_root or ""
    ).strip():
        return
    try:
        async with async_session_factory() as db:
            agent = (
                await db.execute(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id))
            ).scalar_one_or_none()
            if agent is None:
                return
            ok, msg = await dispatch_microsoft_graphrag_corpus(db=db, agent=agent, settings=cfg)
            if not ok:
                logger.warning("microsoft_graphrag_auto_dispatch_failed", agent_id=str(agent_id), msg=msg)
    except Exception as exc:  # noqa: BLE001
        logger.exception("microsoft_graphrag_auto_dispatch_error", agent_id=str(agent_id), error=str(exc))


async def maybe_auto_dispatch_graphrag_corpus(agent_id: UUID, tenant_id: UUID) -> None:
    """Фоновые задачи: при ``MICROSOFT_GRAPHRAG_AUTO_DISPATCH_CORPUS`` и заданном webhook или workspace root."""
    await _dispatch_with_new_session(agent_id, tenant_id)
