from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from pydantic import ValidationError
from sqlalchemy import delete, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.audit import AuditLog
from app.db.models.agent_analysis_job import AgentAnalysisJob
from app.db.models.agent_analysis_recommendation import AgentAnalysisRecommendation
from app.db.models.agent_analysis_report import AgentAnalysisReport
from app.db.session import async_session_factory
from app.schemas.agent_analysis import AnalysisJobCreateRequest
from app.services.agent_analysis.analyzers import ANALYZER_VERSION, analyze_dialog_samples
from app.services.agent_analysis.contracts import AnalyzerRecommendation
from app.services.agent_analysis.data_collector import AnalysisDialogSample, collect_dialog_samples
from app.services.agent_analysis.redaction import redact_text
from app.services.tenant_llm_config import get_decrypted_api_key

logger = structlog.get_logger(__name__)


class ActiveAnalysisJobConflictError(Exception):
    def __init__(self, job: AgentAnalysisJob) -> None:
        super().__init__("У агента уже есть активная задача анализа")
        self.job = job


class TerminalAnalysisJobError(Exception):
    def __init__(self, job: AgentAnalysisJob) -> None:
        super().__init__("Нельзя отменить задачу в terminal-состоянии")
        self.job = job


def _utcnow() -> datetime:
    return datetime.utcnow()


def _compute_period(window_hours: int) -> tuple[datetime, datetime]:
    end_at = _utcnow()
    start_at = end_at - timedelta(hours=window_hours)
    return start_at, end_at


def _to_json_dict(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        try:
            dumped = item.model_dump(mode="json")
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            return None
    return None


def _calculate_kpis(dialogs: list[AnalysisDialogSample]) -> tuple[dict[str, Any], dict[str, int], list[str]]:
    if not dialogs:
        empty = {
            "intervention_rate": 0.0,
            "tool_error_rate": 0.0,
            "tool_argument_mismatch_rate": 0.0,
            "topic_count": 0,
            "recommendation_count": 0,
        }
        return empty, {}, []

    total_dialogs = len(dialogs)
    dialogs_with_manager = sum(1 for item in dialogs if item.has_manager_intervention)
    intervention_rate = dialogs_with_manager / total_dialogs

    tool_events = [event for dialog in dialogs for event in dialog.tool_events]
    tool_errors = [
        event
        for event in tool_events
        if event.error and str(event.error).strip()
    ]
    tool_error_rate = (len(tool_errors) / len(tool_events)) if tool_events else 0.0

    mismatch_errors = 0
    mismatch_markers = ("invalid", "missing", "required", "argument", "validation", "schema")
    for event in tool_errors:
        lower = str(event.error).lower()
        if any(marker in lower for marker in mismatch_markers):
            mismatch_errors += 1
    tool_argument_mismatch_rate = (mismatch_errors / len(tool_events)) if tool_events else 0.0

    topic_counter = Counter()
    for dialog in dialogs:
        if dialog.tool_events:
            topic_counter["tool_interaction"] += 1
        if dialog.has_manager_intervention:
            topic_counter["manager_intervention"] += 1
        if dialog.dominant_language:
            topic_counter[f"lang:{dialog.dominant_language}"] += 1
    top_failure_topics = [name for name, _ in topic_counter.most_common(5)]

    kpis = {
        "intervention_rate": intervention_rate,
        "tool_error_rate": tool_error_rate,
        "tool_argument_mismatch_rate": tool_argument_mismatch_rate,
        "topic_count": 0,
        "recommendation_count": 0,
    }
    return kpis, dict(topic_counter), top_failure_topics


async def _cleanup_expired_analysis_data(db: AsyncSession, *, tenant_id: UUID) -> None:
    settings = get_settings()
    cutoff = _utcnow() - timedelta(days=settings.analysis_reports_ttl_days)

    old_jobs_stmt = select(AgentAnalysisJob.id).where(
        AgentAnalysisJob.tenant_id == tenant_id,
        AgentAnalysisJob.created_at < cutoff,
    )
    old_job_ids = (await db.execute(old_jobs_stmt)).scalars().all()
    if not old_job_ids:
        return

    await db.execute(
        delete(AgentAnalysisRecommendation).where(
            AgentAnalysisRecommendation.tenant_id == tenant_id,
            AgentAnalysisRecommendation.job_id.in_(old_job_ids),
        )
    )
    await db.execute(
        delete(AgentAnalysisReport).where(
            AgentAnalysisReport.tenant_id == tenant_id,
            AgentAnalysisReport.job_id.in_(old_job_ids),
        )
    )
    await db.execute(
        delete(AgentAnalysisJob).where(
            AgentAnalysisJob.tenant_id == tenant_id,
            AgentAnalysisJob.id.in_(old_job_ids),
        )
    )


async def create_analysis_job(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    payload: AnalysisJobCreateRequest,
) -> tuple[AgentAnalysisJob, bool]:
    await _cleanup_expired_analysis_data(db, tenant_id=tenant_id)

    if payload.idempotency_key:
        existing_stmt = (
            select(AgentAnalysisJob)
            .where(
                AgentAnalysisJob.tenant_id == tenant_id,
                AgentAnalysisJob.agent_id == agent_id,
                AgentAnalysisJob.idempotency_key == payload.idempotency_key,
            )
            .order_by(AgentAnalysisJob.created_at.desc())
            .limit(1)
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            return existing, False

    active_stmt = select(AgentAnalysisJob).where(
        AgentAnalysisJob.tenant_id == tenant_id,
        AgentAnalysisJob.agent_id == agent_id,
        AgentAnalysisJob.status.in_(["queued", "running"]),
    ).order_by(AgentAnalysisJob.created_at.desc())
    active_job = (await db.execute(active_stmt)).scalars().first()
    if active_job:
        raise ActiveAnalysisJobConflictError(active_job)

    period_start, period_end = _compute_period(payload.window_hours)
    job = AgentAnalysisJob(
        tenant_id=tenant_id,
        agent_id=agent_id,
        status="queued",
        stage="queued",
        progress_pct=0,
        period_start=period_start,
        period_end=period_end,
        window_hours=payload.window_hours,
        only_with_manager=payload.only_with_manager,
        max_dialogs=payload.max_dialogs,
        history_limit=payload.history_limit,
        max_tokens_per_job=payload.max_tokens_per_job,
        max_llm_requests_per_job=payload.max_llm_requests_per_job,
        idempotency_key=payload.idempotency_key,
        meta_model=payload.meta_model,
        created_by_user_id=user_id,
    )
    db.add(job)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        if payload.idempotency_key:
            existing_stmt = (
                select(AgentAnalysisJob)
                .where(
                    AgentAnalysisJob.tenant_id == tenant_id,
                    AgentAnalysisJob.agent_id == agent_id,
                    AgentAnalysisJob.idempotency_key == payload.idempotency_key,
                )
                .order_by(AgentAnalysisJob.created_at.desc())
                .limit(1)
            )
            existing = (await db.execute(existing_stmt)).scalar_one_or_none()
            if existing:
                return existing, False
        raise
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="analysis_job_started",
            entity_type="analysis_job",
            entity_id=str(job.id),
            metadata_={
                "agent_id": str(agent_id),
                "idempotency_key": payload.idempotency_key,
                "window_hours": payload.window_hours,
            },
        )
    )
    return job, True


async def get_analysis_job(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    job_id: UUID,
) -> AgentAnalysisJob | None:
    stmt = select(AgentAnalysisJob).where(
        AgentAnalysisJob.id == job_id,
        AgentAnalysisJob.tenant_id == tenant_id,
        AgentAnalysisJob.agent_id == agent_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_analysis_jobs(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    limit: int = 30,
    cursor: UUID | None = None,
) -> list[AgentAnalysisJob]:
    stmt = select(AgentAnalysisJob).where(
        AgentAnalysisJob.tenant_id == tenant_id,
        AgentAnalysisJob.agent_id == agent_id,
    )
    if cursor:
        cursor_stmt = select(AgentAnalysisJob.created_at).where(
            AgentAnalysisJob.id == cursor,
            AgentAnalysisJob.tenant_id == tenant_id,
            AgentAnalysisJob.agent_id == agent_id,
        )
        cursor_created_at = (await db.execute(cursor_stmt)).scalar_one_or_none()
        if cursor_created_at:
            stmt = stmt.where(AgentAnalysisJob.created_at < cursor_created_at)
    stmt = stmt.order_by(AgentAnalysisJob.created_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def get_report_for_job(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    job_id: UUID,
) -> AgentAnalysisReport | None:
    stmt = select(AgentAnalysisReport).where(
        AgentAnalysisReport.tenant_id == tenant_id,
        AgentAnalysisReport.agent_id == agent_id,
        AgentAnalysisReport.job_id == job_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_recommendations(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    category: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AgentAnalysisRecommendation], int]:
    filters = [
        AgentAnalysisRecommendation.tenant_id == tenant_id,
        AgentAnalysisRecommendation.agent_id == agent_id,
    ]
    if category:
        filters.append(AgentAnalysisRecommendation.category == category)
    if status:
        filters.append(AgentAnalysisRecommendation.status == status)
    total_stmt = select(func.count(AgentAnalysisRecommendation.id)).where(*filters)
    total = int((await db.execute(total_stmt)).scalar_one())
    stmt = select(AgentAnalysisRecommendation).where(*filters)
    stmt = stmt.order_by(
        desc(AgentAnalysisRecommendation.created_at),
        desc(AgentAnalysisRecommendation.confidence),
    ).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all()), total


async def get_recommendation(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    recommendation_id: UUID,
) -> AgentAnalysisRecommendation | None:
    stmt = select(AgentAnalysisRecommendation).where(
        AgentAnalysisRecommendation.id == recommendation_id,
        AgentAnalysisRecommendation.tenant_id == tenant_id,
        AgentAnalysisRecommendation.agent_id == agent_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def review_recommendation(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    recommendation_id: UUID,
    status: str,
    review_comment: str | None,
    reviewed_by_user_id: UUID,
) -> AgentAnalysisRecommendation | None:
    stmt = select(AgentAnalysisRecommendation).where(
        AgentAnalysisRecommendation.id == recommendation_id,
        AgentAnalysisRecommendation.tenant_id == tenant_id,
        AgentAnalysisRecommendation.agent_id == agent_id,
    )
    recommendation = (await db.execute(stmt)).scalar_one_or_none()
    if recommendation is None:
        return None
    if recommendation.status == status and recommendation.reviewer_comment == review_comment:
        return recommendation
    recommendation.status = status
    recommendation.reviewer_comment = review_comment
    recommendation.reviewed_at = _utcnow()
    recommendation.reviewed_by_user_id = reviewed_by_user_id
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=reviewed_by_user_id,
            action="analysis_recommendation_reviewed",
            entity_type="analysis_recommendation",
            entity_id=str(recommendation.id),
            metadata_={
                "agent_id": str(agent_id),
                "status": status,
            },
        )
    )
    await db.flush()
    return recommendation


async def cancel_analysis_job(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    job_id: UUID,
    cancelled_by_user_id: UUID,
) -> AgentAnalysisJob | None:
    job = await get_analysis_job(db, tenant_id=tenant_id, agent_id=agent_id, job_id=job_id)
    if job is None:
        return None
    if job.status in {"succeeded", "failed", "cancelled"}:
        raise TerminalAnalysisJobError(job)
    previous_status = job.status
    job.status = "cancelled"
    job.stage = "cancelled"
    job.progress_pct = 100
    job.finished_at = _utcnow()
    job.cancelled_by_user_id = cancelled_by_user_id
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=cancelled_by_user_id,
            action="analysis_job_cancelled",
            entity_type="analysis_job",
            entity_id=str(job.id),
            metadata_={
                "agent_id": str(agent_id),
                "previous_status": previous_status,
            },
        )
    )
    await db.flush()
    return job


def schedule_analysis_job(job_id: UUID) -> None:
    async def _runner() -> None:
        try:
            await run_analysis_job(job_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("analysis_job_runner_failed", job_id=str(job_id), error=str(exc))

    asyncio.create_task(_runner())


async def _fail_job(db: AsyncSession, job: AgentAnalysisJob, error: str) -> None:
    # If the session is in failed transaction state (e.g., flush error),
    # rollback first so we can reliably persist failed status.
    try:
        await db.rollback()
    except Exception:  # noqa: BLE001
        pass

    fresh_job = (
        await db.execute(
            select(AgentAnalysisJob).where(AgentAnalysisJob.id == job.id)
        )
    ).scalar_one_or_none()
    if fresh_job is None:
        return

    fresh_job.status = "failed"
    fresh_job.stage = "failed"
    fresh_job.progress_pct = 100
    fresh_job.error_message = redact_text(error)[:2000]
    fresh_job.finished_at = _utcnow()
    await db.commit()


async def _persist_recommendations(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    job_id: UUID,
    report_id: UUID,
    recommendations: list[dict[str, Any]],
) -> None:
    rows: list[AgentAnalysisRecommendation] = []
    for idx, rec in enumerate(recommendations):
        if not isinstance(rec, dict):
            raise RuntimeError(f"Invalid analyzer recommendation payload at index {idx}: expected object")
        try:
            normalized = AnalyzerRecommendation.model_validate(rec)
        except ValidationError as exc:
            raise RuntimeError(f"Invalid analyzer recommendation payload at index {idx}") from exc
        rows.append(
            AgentAnalysisRecommendation(
                tenant_id=tenant_id,
                agent_id=agent_id,
                job_id=job_id,
                report_id=report_id,
                category=normalized.category,
                priority=normalized.priority,
                confidence=normalized.confidence,
                title=normalized.title,
                reasoning=normalized.reasoning,
                suggestion=normalized.suggestion,
                impact=normalized.impact,
                evidence_dialog_ids=[str(item) for item in normalized.evidence_dialog_ids],
                evidence=[item.model_dump(mode="json") for item in normalized.evidence],
            )
        )
    if rows:
        db.add_all(rows)
        await db.flush()


async def run_analysis_job(job_id: UUID) -> None:
    settings = get_settings()
    async with async_session_factory() as db:
        job = (await db.execute(select(AgentAnalysisJob).where(AgentAnalysisJob.id == job_id))).scalar_one_or_none()
        if job is None:
            return
        if job.status in {"cancelled", "succeeded", "failed"}:
            return

        job.status = "running"
        job.stage = "collecting"
        job.progress_pct = 5
        job.started_at = _utcnow()
        await db.commit()

        try:
            dialogs = await collect_dialog_samples(
                db,
                tenant_id=job.tenant_id,
                agent_id=job.agent_id,
                period_start=job.period_start,
                period_end=job.period_end,
                history_limit=job.history_limit,
                max_dialogs=job.max_dialogs,
                only_with_manager=job.only_with_manager,
            )

            await db.refresh(job)
            if job.status == "cancelled":
                return

            job.stage = "analyzing"
            job.progress_pct = 45
            job.analysis_as_of = _utcnow()
            await db.commit()

            model_name = job.meta_model or settings.pydanticai_default_model
            openai_api_key = await get_decrypted_api_key(db, job.tenant_id)
            if not openai_api_key:
                raise RuntimeError(
                    "API-ключ OpenAI не настроен для организации. Установите его в Настройках организации → Ключ LLM."
                )

            if len(dialogs) > job.max_dialogs:
                dialogs = dialogs[: job.max_dialogs]

            analyzer_run = await analyze_dialog_samples(
                dialogs,
                model_name=model_name,
                openai_api_key=openai_api_key,
                max_llm_requests=min(job.max_llm_requests_per_job, 100),
            )

            await db.refresh(job)
            if job.status == "cancelled":
                return

            analyzer_output = analyzer_run.output
            topics_json = [topic for topic in (_to_json_dict(item) for item in analyzer_output.topics) if topic]
            recommendations_json = [
                rec for rec in (_to_json_dict(item) for item in analyzer_output.recommendations) if rec
            ]
            job.llm_requests_used = analyzer_run.request_count
            job.tokens_used = analyzer_run.prompt_tokens + analyzer_run.completion_tokens

            if job.llm_requests_used > job.max_llm_requests_per_job:
                raise RuntimeError("Превышен лимит LLM-запросов для задачи анализа.")
            if job.tokens_used >= job.max_tokens_per_job:
                raise RuntimeError("Превышен лимит токенов для задачи анализа.")

            kpis, topic_counter, top_failure_topics = _calculate_kpis(dialogs)
            kpis["topic_count"] = len(topics_json)
            kpis["recommendation_count"] = len(recommendations_json)

            recommendation_count_by_category = Counter()
            for item in recommendations_json:
                recommendation_count_by_category[str(item.get("category", "unknown"))] += 1

            job.stage = "persisting"
            job.progress_pct = 75
            await db.commit()

            report = AgentAnalysisReport(
                tenant_id=job.tenant_id,
                agent_id=job.agent_id,
                job_id=job.id,
                period_start=job.period_start,
                period_end=job.period_end,
                window_hours=job.window_hours,
                analysis_as_of=job.analysis_as_of or _utcnow(),
                analyzer_version=settings.analysis_analyzer_version or ANALYZER_VERSION,
                model_name=model_name,
                summary=analyzer_output.summary,
                kpis=kpis,
                topics=topics_json,
                top_failure_topics=top_failure_topics,
                recommendation_count_by_category=dict(recommendation_count_by_category),
                raw_output={
                    "topic_counter": topic_counter,
                    "dialogs_analyzed": len(dialogs),
                },
            )
            db.add(report)
            await db.flush()

            await _persist_recommendations(
                db,
                tenant_id=job.tenant_id,
                agent_id=job.agent_id,
                job_id=job.id,
                report_id=report.id,
                recommendations=recommendations_json,
            )

            await db.refresh(job)
            if job.status == "cancelled":
                return

            job.report_id = report.id
            job.status = "succeeded"
            job.stage = "done"
            job.progress_pct = 100
            job.finished_at = _utcnow()
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            await _fail_job(db, job, str(exc))
