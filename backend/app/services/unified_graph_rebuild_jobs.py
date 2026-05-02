from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.agent import Agent
from app.db.models.unified_graph_rebuild_job import UnifiedGraphRebuildJob
from app.db.session import async_session_factory
from app.services.agent_unified_graph import (
    compute_node_embeddings,
    enrich_semantic_relations,
    materialize_unified_graph,
)
from app.services.graphrag_export.corpus_dispatch import dispatch_microsoft_graphrag_corpus

logger = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_unified_graph_rebuild_job(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    job_id: UUID,
) -> UnifiedGraphRebuildJob | None:
    stmt = select(UnifiedGraphRebuildJob).where(
        UnifiedGraphRebuildJob.id == job_id,
        UnifiedGraphRebuildJob.tenant_id == tenant_id,
        UnifiedGraphRebuildJob.agent_id == agent_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_active_unified_graph_rebuild_job(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
) -> UnifiedGraphRebuildJob | None:
    stmt = (
        select(UnifiedGraphRebuildJob)
        .where(
            UnifiedGraphRebuildJob.tenant_id == tenant_id,
            UnifiedGraphRebuildJob.agent_id == agent_id,
            UnifiedGraphRebuildJob.status.in_(["queued", "running"]),
        )
        .order_by(UnifiedGraphRebuildJob.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_latest_unified_graph_rebuild_job(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
) -> UnifiedGraphRebuildJob | None:
    stmt = (
        select(UnifiedGraphRebuildJob)
        .where(
            UnifiedGraphRebuildJob.tenant_id == tenant_id,
            UnifiedGraphRebuildJob.agent_id == agent_id,
        )
        .order_by(UnifiedGraphRebuildJob.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_unified_graph_rebuild_job(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent: Agent,
    active_sqns_only: bool,
    created_by_user_id: UUID | None,
) -> tuple[UnifiedGraphRebuildJob, bool]:
    active_job = await get_active_unified_graph_rebuild_job(
        db,
        tenant_id=tenant_id,
        agent_id=agent.id,
    )
    if active_job is not None:
        return active_job, False

    job = UnifiedGraphRebuildJob(
        tenant_id=tenant_id,
        agent_id=agent.id,
        status="queued",
        stage="queued",
        progress_pct=0,
        active_sqns_only=active_sqns_only,
        message=None,
        error_message=None,
        started_at=None,
        finished_at=None,
        created_by_user_id=created_by_user_id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job, True


def run_unified_graph_rebuild_job_in_background(job_id: UUID) -> None:
    async def _runner() -> None:
        try:
            await _process_unified_graph_rebuild_job(job_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "unified_graph_rebuild_job_runner_failed",
                job_id=str(job_id),
                error=str(exc),
            )

    asyncio.create_task(_runner())


async def _mark_job_failed(db: AsyncSession, *, job_id: UUID, error: str) -> None:
    try:
        await db.rollback()
    except Exception:  # noqa: BLE001
        pass

    job = await db.get(UnifiedGraphRebuildJob, job_id)
    if job is None:
        return

    job.status = "failed"
    job.stage = "failed"
    job.progress_pct = 100
    job.message = None
    job.error_message = (error or "unexpected_error")[:4000]
    job.finished_at = _utcnow()
    await db.commit()


async def _process_unified_graph_rebuild_job(job_id: UUID) -> None:
    async with async_session_factory() as db:
        job = await db.get(UnifiedGraphRebuildJob, job_id)
        if job is None:
            return

        stmt = select(Agent).where(Agent.id == job.agent_id, Agent.tenant_id == job.tenant_id)
        agent = (await db.execute(stmt)).scalar_one_or_none()
        if agent is None:
            await _mark_job_failed(db, job_id=job_id, error="agent_not_found")
            return

        settings = get_settings()
        ws_root = (settings.microsoft_graphrag_workspace_root or "").strip()
        job.status = "running"
        job.stage = "materializing"
        job.progress_pct = 5
        job.message = None
        job.error_message = None
        job.started_at = _utcnow()
        await db.commit()

        # Слой 1 — структурный материализатор (быстро, без LLM).
        # Граф визуализации сразу становится корректным. GraphRAG-индексация
        # запускается следом для рантайм-инструмента query_microsoft_graphrag.
        try:
            mat = await materialize_unified_graph(
                db, tenant_id=job.tenant_id, agent_id=job.agent_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "unified_graph_materialize_failed",
                job_id=str(job_id),
                agent_id=str(job.agent_id),
                error=str(exc),
            )
            await _mark_job_failed(db, job_id=job_id, error=f"materialize: {exc}"[:4000])
            return

        # Слой 1.5 — эмбеддинги для узлов (нужны cosine-обогащению).
        # Считаются только для узлов с устаревшим хешем контента.
        try:
            emb = await compute_node_embeddings(
                db, tenant_id=job.tenant_id, agent_id=job.agent_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "unified_graph_embeddings_failed",
                job_id=str(job_id),
                agent_id=str(job.agent_id),
                error=str(exc),
            )
            emb = None

        # Слой 2 — семантическое обогащение (keyword + cosine, без новых узлов).
        try:
            enrich = await enrich_semantic_relations(
                db, tenant_id=job.tenant_id, agent_id=job.agent_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "unified_graph_enrich_failed",
                job_id=str(job_id),
                agent_id=str(job.agent_id),
                error=str(exc),
            )
            # Не валим весь rebuild — структурный слой уже на месте.
            enrich = None

        job.stage = "indexing" if ws_root else "dispatching"
        job.progress_pct = 30
        enrich_part = (
            f", +{enrich.relations} семантических связей" if enrich else ""
        )
        job.message = (
            f"Структура: {mat.nodes} узлов, {mat.relations} связей{enrich_part}. "
            "Индексация GraphRAG…"
        )
        await db.commit()

        try:
            ok, message = await dispatch_microsoft_graphrag_corpus(
                db=db,
                agent=agent,
                settings=settings,
                active_sqns_only=bool(job.active_sqns_only),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "unified_graph_rebuild_job_failed",
                job_id=str(job_id),
                agent_id=str(job.agent_id),
                tenant_id=str(job.tenant_id),
                error=str(exc),
            )
            await _mark_job_failed(db, job_id=job_id, error=str(exc) or exc.__class__.__name__)
            return

        if not ok:
            job.status = "failed"
            job.stage = "failed"
            job.progress_pct = 100
            job.message = None
            job.error_message = (message or "rebuild_failed")[:4000]
            job.finished_at = _utcnow()
            await db.commit()
            return

        job.status = "succeeded"
        job.stage = "done"
        job.progress_pct = 100
        job.message = (message or "ok")[:4000]
        job.error_message = None
        job.finished_at = _utcnow()
        await db.commit()
