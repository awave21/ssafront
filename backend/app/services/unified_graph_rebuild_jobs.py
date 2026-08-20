from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.agent import Agent
from app.db.models.script_flow import ScriptFlow
from app.db.models.unified_graph_rebuild_job import UnifiedGraphRebuildJob
from app.db.session import async_session_factory
from app.services.agent_unified_graph import (
    compute_node_embeddings,
    enrich_semantic_relations,
    materialize_unified_graph,
)
from app.services.graphrag_export.corpus_dispatch import dispatch_graphrag_corpus
from app.services.graph.sqns_neo4j_sync import sync_sqns_to_neo4j
from app.services.tenant_llm_config import get_decrypted_api_key
from sqlalchemy import func, update

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


async def _count_pending_flows(agent_id: UUID) -> tuple[int, int]:
    """Returns (pending+indexing, total_published) для прогресса."""
    async with async_session_factory() as db:
        pending = await db.scalar(
            select(func.count(ScriptFlow.id)).where(
                ScriptFlow.agent_id == agent_id,
                ScriptFlow.published_version.isnot(None),
                ScriptFlow.published_version > 0,
                ScriptFlow.index_status.in_(["pending", "indexing"]),
            )
        )
        total = await db.scalar(
            select(func.count(ScriptFlow.id)).where(
                ScriptFlow.agent_id == agent_id,
                ScriptFlow.published_version.isnot(None),
                ScriptFlow.published_version > 0,
            )
        )
        return int(pending or 0), int(total or 0)


async def _update_job(job_id: UUID, **fields) -> None:
    async with async_session_factory() as db:
        job = await db.get(UnifiedGraphRebuildJob, job_id)
        if job is None:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        await db.commit()


async def _process_unified_graph_rebuild_job(job_id: UUID) -> None:
    """Полный sweep по агенту: SQNS + переиндексация скрипт-флоу + повторный SQNS.

    Порядок важен: :Service/:Specialist должны быть в Neo4j ДО индексации flows,
    чтобы fuzzy-match создавал рёбра :COVERS_SERVICE/:HAS_SPECIALIST. После
    flows прогоняем SQNS повторно — теперь :Service embedding обогащается
    контекстом канвас-нод (через новые рёбра).

    Stages:
      1. SQNS sync — pre-flow (creates :Service/:Specialist) (5→15%)
      2. mark all published flows as pending (15%)
      3. poll until all flows reach 'indexed' (15→75%)
      4. SQNS sync — post-flow (refresh embeddings with flow context) (75→95%)
      5. done (100%)
    """
    async with async_session_factory() as db:
        job = await db.get(UnifiedGraphRebuildJob, job_id)
        if job is None:
            return

        stmt = select(Agent).where(Agent.id == job.agent_id, Agent.tenant_id == job.tenant_id)
        agent = (await db.execute(stmt)).scalar_one_or_none()
        if agent is None:
            await _mark_job_failed(db, job_id=job_id, error="agent_not_found")
            return

        agent_id = job.agent_id
        tenant_id = job.tenant_id

        job.status = "running"
        job.stage = "syncing_sqns_pre"
        job.progress_pct = 5
        job.message = "Синхронизация SQNS услуг/специалистов в Neo4j (pre-flow)…"
        job.error_message = None
        job.started_at = _utcnow()
        await db.commit()

        # Stage 1: SQNS sync FIRST — creates :Service/:Specialist nodes
        # so that fuzzy-match in flow indexing can write COVERS_SERVICE edges.
        try:
            openai_api_key = await get_decrypted_api_key(db, tenant_id)
            await sync_sqns_to_neo4j(
                db=db,
                agent_id=agent_id,
                tenant_id=tenant_id,
                openai_api_key=openai_api_key,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "unified_graph_rebuild_sqns_pre_failed",
                job_id=str(job_id),
                agent_id=str(agent_id),
                error=str(exc),
            )
            await _mark_job_failed(db, job_id=job_id, error=f"sqns_sync_pre: {exc}"[:4000])
            return

        await _update_job(
            job_id,
            stage="reindexing_flows",
            progress_pct=15,
            message="Постановка опубликованных потоков в очередь индексации…",
        )

        # Stage 2: re-queue all published flows.
        try:
            await db.execute(
                update(ScriptFlow)
                .where(
                    ScriptFlow.agent_id == agent_id,
                    ScriptFlow.published_version.isnot(None),
                    ScriptFlow.published_version > 0,
                )
                .values(index_status="pending", index_retry_count=0, index_error=None)
            )
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "unified_graph_rebuild_requeue_failed",
                job_id=str(job_id),
                agent_id=str(agent_id),
                error=str(exc),
            )
            await _mark_job_failed(db, job_id=job_id, error=f"requeue: {exc}"[:4000])
            return

    # Stage 3: poll until all flows are indexed (worker processes them in parallel).
    max_wait_seconds = 1200  # 20 minutes hard limit
    poll_interval = 5
    waited = 0
    initial_pending, total_flows = await _count_pending_flows(agent_id)
    while waited < max_wait_seconds:
        pending, _ = await _count_pending_flows(agent_id)
        if pending == 0:
            break
        # progress: 15% → 75% линейно по доле обработанных
        if total_flows > 0:
            done_ratio = max(0.0, (total_flows - pending) / total_flows)
        else:
            done_ratio = 0.0
        pct = int(15 + done_ratio * 60)
        await _update_job(
            job_id,
            stage="reindexing_flows",
            progress_pct=pct,
            message=f"Индексация потоков: {total_flows - pending}/{total_flows}",
        )
        await asyncio.sleep(poll_interval)
        waited += poll_interval
    else:
        async with async_session_factory() as db:
            await _mark_job_failed(db, job_id=job_id, error="reindex_timeout")
        return

    # Stage 4: SQNS sync POST-flow — обогащает :Service/:Specialist embedding'и
    # контекстом канвас-нод через новосозданные рёбра :COVERS_SERVICE/:HAS_SPECIALIST.
    await _update_job(
        job_id,
        stage="syncing_sqns_post",
        progress_pct=75,
        message="Обновление embedding'ов услуг и специалистов с контекстом скриптов…",
    )
    try:
        async with async_session_factory() as db:
            openai_api_key = await get_decrypted_api_key(db, tenant_id)
            await sync_sqns_to_neo4j(
                db=db,
                agent_id=agent_id,
                tenant_id=tenant_id,
                openai_api_key=openai_api_key,
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "unified_graph_rebuild_sqns_post_failed",
            job_id=str(job_id),
            agent_id=str(agent_id),
            error=str(exc),
        )
        async with async_session_factory() as db:
            await _mark_job_failed(db, job_id=job_id, error=f"sqns_sync_post: {exc}"[:4000])
        return

    # Stage 5: done.
    await _update_job(
        job_id,
        status="succeeded",
        stage="done",
        progress_pct=100,
        message=f"Готово. Реиндексировано потоков: {total_flows}.",
        error_message=None,
        finished_at=_utcnow(),
    )
