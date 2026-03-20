from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.db.models.agent_analysis_job import AgentAnalysisJob
from app.db.models.agent_analysis_recommendation import AgentAnalysisRecommendation
from app.db.models.agent_analysis_report import AgentAnalysisReport
from app.db.session import get_db
from app.schemas.agent_analysis import (
    AnalysisJobCancelResponse,
    AnalysisJobCreateRequest,
    AnalysisJobRead,
    AnalysisJobStartResponse,
    AnalysisJobsListResponse,
    AnalysisJobsListData,
    AnalysisKpiSummary,
    AnalysisRecommendationsListResponse,
    AnalysisRecommendationsListData,
    AnalysisRecommendationRead,
    AnalysisRecommendationResponse,
    AnalysisReportPayload,
    AnalysisReportMeta,
    AnalysisReportResponse,
    RecommendationCategory,
    RecommendationStatus,
    RecommendationReviewRequest,
    RecommendationEvidence,
)
from app.schemas.auth import AuthContext
from app.services.agent_analysis.orchestrator import (
    ActiveAnalysisJobConflictError,
    TerminalAnalysisJobError,
    cancel_analysis_job,
    create_analysis_job,
    get_analysis_job,
    get_recommendation,
    get_report_for_job,
    list_analysis_jobs,
    list_recommendations,
    review_recommendation,
    schedule_analysis_job,
)

router = APIRouter()
_ANALYSIS_OVERRIDE_ROLES = {"owner", "admin", "system"}


def _error_detail(
    *,
    error: str,
    message: str,
    detail: str | dict[str, object] | None = None,
    field_errors: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    return {
        "error": error,
        "message": message,
        "detail": detail,
        "field_errors": field_errors,
    }


def _can_manage_job(user: AuthContext, job: AgentAnalysisJob) -> bool:
    if user.role in _ANALYSIS_OVERRIDE_ROLES:
        return True
    if job.created_by_user_id is None:
        return False
    return job.created_by_user_id == user.user_id


def _build_job_read(job) -> AnalysisJobRead:
    return AnalysisJobRead.model_validate(job)


def _build_recommendation_read(rec: AgentAnalysisRecommendation) -> AnalysisRecommendationRead:
    evidence_rows = rec.evidence if isinstance(rec.evidence, list) else []
    return AnalysisRecommendationRead(
        id=rec.id,
        category=rec.category,
        priority=rec.priority,
        confidence=rec.confidence,
        title=rec.title,
        reasoning=rec.reasoning,
        suggestion=rec.suggestion,
        impact=rec.impact,
        evidence_dialog_ids=[str(item) for item in (rec.evidence_dialog_ids or [])],
        evidence=[
            RecommendationEvidence.model_validate(item)
            for item in evidence_rows
            if isinstance(item, dict)
        ],
        status=rec.status,
        review_comment=rec.reviewer_comment,
        reviewed_at=rec.reviewed_at,
        reviewed_by_user_id=rec.reviewed_by_user_id,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


def _build_report_read(report: AgentAnalysisReport) -> AnalysisReportPayload:
    kpis_raw = report.kpis if isinstance(report.kpis, dict) else {}
    return AnalysisReportPayload(
        summary=report.summary,
        kpis=AnalysisKpiSummary(
            intervention_rate=float(kpis_raw.get("intervention_rate", 0.0)),
            tool_error_rate=float(kpis_raw.get("tool_error_rate", 0.0)),
            tool_argument_mismatch_rate=float(kpis_raw.get("tool_argument_mismatch_rate", 0.0)),
            topic_count=int(kpis_raw.get("topic_count", 0)),
            recommendation_count=int(kpis_raw.get("recommendation_count", 0)),
        ),
        topics=report.topics if isinstance(report.topics, list) else [],
        top_failure_topics=(
            [str(item) for item in report.top_failure_topics]
            if isinstance(report.top_failure_topics, list)
            else []
        ),
        meta=AnalysisReportMeta(
            recommendation_count_by_category=(
                report.recommendation_count_by_category
                if isinstance(report.recommendation_count_by_category, dict)
                else {}
            ),
            created_at=report.created_at,
            report_id=report.id,
            job_id=report.job_id,
            period_start=report.period_start,
            period_end=report.period_end,
            window_hours=report.window_hours,
            analysis_as_of=report.analysis_as_of,
            analyzer_version=report.analyzer_version,
            model_name=report.model_name,
        ),
    )


def _build_job_snapshot(job: AgentAnalysisJob) -> dict[str, object]:
    return {
        "id": str(job.id),
        "status": job.status,
        "stage": job.stage,
        "progress_pct": job.progress_pct,
    }


def _raise_analysis_error(
    *,
    status_code: int,
    error: str,
    message: str,
    detail: str | dict[str, object] | None = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=_error_detail(error=error, message=message, detail=detail),
    )


@router.post(
    "/analysis/jobs",
    response_model=AnalysisJobStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_analysis_job(
    agent_id: UUID,
    payload: AnalysisJobCreateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> AnalysisJobStartResponse:
    await get_agent_or_404(agent_id, db, user)
    try:
        job, is_new = await create_analysis_job(
            db,
            tenant_id=user.tenant_id,
            agent_id=agent_id,
            user_id=user.user_id,
            payload=payload,
        )
    except ActiveAnalysisJobConflictError as exc:
        _raise_analysis_error(
            status_code=status.HTTP_409_CONFLICT,
            error="analysis_job_conflict",
            message="У агента уже есть активная задача анализа",
            detail={"blocking_job": _build_job_snapshot(exc.job)},
        )

    await db.commit()
    await db.refresh(job)
    if is_new and job.status == "queued":
        schedule_analysis_job(job.id)
    if not is_new:
        response.status_code = status.HTTP_200_OK

    return AnalysisJobStartResponse(data=_build_job_read(job))


@router.get("/analysis/jobs", response_model=AnalysisJobsListResponse)
async def get_analysis_jobs(
    agent_id: UUID,
    limit: int = Query(default=30, ge=1, le=100),
    cursor: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> AnalysisJobsListResponse:
    await get_agent_or_404(agent_id, db, user)
    jobs = await list_analysis_jobs(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        limit=limit + 1,
        cursor=cursor,
    )
    has_more = len(jobs) > limit
    if has_more:
        jobs = jobs[:limit]
    next_cursor = str(jobs[-1].id) if has_more and jobs else None
    return AnalysisJobsListResponse(
        data=AnalysisJobsListData(
            items=[_build_job_read(item) for item in jobs],
            next_cursor=next_cursor,
        )
    )


@router.get("/analysis/jobs/{job_id}", response_model=AnalysisJobStartResponse)
async def get_analysis_job_status(
    agent_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> AnalysisJobStartResponse:
    await get_agent_or_404(agent_id, db, user)
    job = await get_analysis_job(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        job_id=job_id,
    )
    if job is None:
        _raise_analysis_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error="analysis_job_not_found",
            message="Analysis job not found",
            detail="Analysis job not found",
        )
    return AnalysisJobStartResponse(data=_build_job_read(job))


@router.get("/analysis/jobs/{job_id}/report", response_model=AnalysisReportResponse)
async def get_analysis_report(
    agent_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> AnalysisReportResponse:
    await get_agent_or_404(agent_id, db, user)
    job = await get_analysis_job(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        job_id=job_id,
    )
    if job is None:
        _raise_analysis_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error="analysis_job_not_found",
            message="Analysis job not found",
            detail="Analysis job not found",
        )
    if job.status != "succeeded":
        _raise_analysis_error(
            status_code=status.HTTP_409_CONFLICT,
            error="report_not_ready",
            message="Report is not ready until job succeeds",
            detail={"job": _build_job_snapshot(job)},
        )
    report = await get_report_for_job(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        job_id=job_id,
    )
    if report is None:
        _raise_analysis_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="report_generation_incomplete",
            message="Job succeeded but report is missing",
            detail={"job": _build_job_snapshot(job)},
        )
    return AnalysisReportResponse(data=_build_report_read(report))


@router.post("/analysis/jobs/{job_id}/cancel", response_model=AnalysisJobCancelResponse)
async def cancel_job(
    agent_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> AnalysisJobCancelResponse:
    await get_agent_or_404(agent_id, db, user)
    target = await get_analysis_job(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        job_id=job_id,
    )
    if target is None:
        _raise_analysis_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error="analysis_job_not_found",
            message="Analysis job not found",
            detail="Analysis job not found",
        )
    if not _can_manage_job(user, target):
        _raise_analysis_error(
            status_code=status.HTTP_403_FORBIDDEN,
            error="analysis_job_access_denied",
            message="Only job owner or elevated role can cancel this analysis job",
            detail={"job": _build_job_snapshot(target)},
        )
    try:
        job = await cancel_analysis_job(
            db,
            tenant_id=user.tenant_id,
            agent_id=agent_id,
            job_id=job_id,
            cancelled_by_user_id=user.user_id,
        )
    except TerminalAnalysisJobError as exc:
        _raise_analysis_error(
            status_code=status.HTTP_409_CONFLICT,
            error="analysis_job_terminal",
            message="Job is already in terminal state and cannot be cancelled",
            detail={"job": _build_job_snapshot(exc.job)},
        )
    if job is None:
        _raise_analysis_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error="analysis_job_not_found",
            message="Analysis job not found",
            detail="Analysis job not found",
        )
    await db.commit()
    await db.refresh(job)
    return AnalysisJobCancelResponse(data=_build_job_read(job))


@router.get("/analysis/recommendations", response_model=AnalysisRecommendationsListResponse)
async def get_recommendations(
    agent_id: UUID,
    category: RecommendationCategory | None = Query(default=None),
    status_filter: RecommendationStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> AnalysisRecommendationsListResponse:
    await get_agent_or_404(agent_id, db, user)
    recommendations, total = await list_recommendations(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        category=category,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return AnalysisRecommendationsListResponse(
        data=AnalysisRecommendationsListData(
            items=[_build_recommendation_read(item) for item in recommendations],
            total=total,
            limit=limit,
            offset=offset,
        )
    )


@router.post(
    "/analysis/recommendations/{recommendation_id}/review",
    response_model=AnalysisRecommendationResponse,
)
async def review_recommendation_endpoint(
    agent_id: UUID,
    recommendation_id: UUID,
    payload: RecommendationReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> AnalysisRecommendationResponse:
    await get_agent_or_404(agent_id, db, user)
    current = await get_recommendation(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        recommendation_id=recommendation_id,
    )
    if current is None:
        _raise_analysis_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error="recommendation_not_found",
            message="Recommendation not found",
            detail="Recommendation not found",
        )
    owner_job = await get_analysis_job(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        job_id=current.job_id,
    )
    if owner_job is None:
        _raise_analysis_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error="analysis_job_not_found",
            message="Analysis job not found",
            detail="Analysis job not found",
        )
    if not _can_manage_job(user, owner_job):
        _raise_analysis_error(
            status_code=status.HTTP_403_FORBIDDEN,
            error="analysis_recommendation_access_denied",
            message="Only job owner or elevated role can review this recommendation",
            detail={"job": _build_job_snapshot(owner_job)},
        )
    recommendation = await review_recommendation(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        recommendation_id=recommendation_id,
        status=payload.status,
        review_comment=payload.review_comment,
        reviewed_by_user_id=user.user_id,
    )
    if recommendation is None:
        _raise_analysis_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error="recommendation_not_found",
            message="Recommendation not found",
            detail="Recommendation not found",
        )
    await db.commit()
    await db.refresh(recommendation)
    return AnalysisRecommendationResponse(data=_build_recommendation_read(recommendation))
