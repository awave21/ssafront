from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
RecommendationCategory = Literal[
    "system_prompt",
    "tool_needed",
    "tool_description_fix",
    "knowledge_or_script_gap",
]
RecommendationPriority = Literal["high", "medium", "low"]
RecommendationStatus = Literal["open", "accepted", "rejected"]


class AnalysisJobCreateRequest(BaseModel):
    window_hours: int = Field(
        default=24,
        ge=24,
        le=168,
        description="Окно анализа в часах. Допустимо только 24..168 (от суток до недели).",
    )
    max_dialogs: int = Field(
        default=250,
        ge=10,
        le=5000,
        description="Максимум диалогов в одном запуске для контроля бюджета.",
    )
    history_limit: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Сколько сообщений брать из каждого диалога.",
    )
    only_with_manager: bool = Field(
        default=True,
        description="Если true — анализировать только диалоги с вмешательством менеджера.",
    )
    max_tokens_per_job: int = Field(
        default=150_000,
        ge=5_000,
        le=5_000_000,
        description="Максимум токенов для всех LLM-запросов в рамках одной задачи.",
    )
    max_llm_requests_per_job: int = Field(
        default=40,
        ge=1,
        le=500,
        description="Максимум LLM-запросов на задачу анализа.",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=200,
        description="Ключ идемпотентности для дедупликации одинаковых запусков.",
    )
    meta_model: str | None = Field(
        default="openai:gpt-5.2",
        description="Модель аналитика. По умолчанию используется размышляющая OpenAI-модель 5.",
    )


class TopicSummary(BaseModel):
    name: str = Field(..., description="Название темы.")
    share: float = Field(..., ge=0, le=1, description="Доля темы от числа проанализированных диалогов.")
    dialogs_count: int = Field(..., ge=0, description="Количество диалогов в теме.")
    health: Literal["good", "warning", "critical"] = Field(
        ...,
        description="Оценка здоровья темы по качеству обработки.",
    )


class RecommendationEvidence(BaseModel):
    dialog_id: str = Field(..., description="ID диалога, подтверждающего рекомендацию.")
    run_id: UUID | None = Field(None, description="ID run, если применимо.")
    message_id: UUID | None = Field(None, description="ID сообщения, если применимо.")
    excerpt: str | None = Field(
        None,
        description="Короткий обезличенный фрагмент сообщения как контекст.",
    )


class AnalysisRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: RecommendationCategory
    priority: RecommendationPriority
    confidence: float = Field(..., ge=0, le=1)
    title: str
    reasoning: str
    suggestion: str
    impact: str | None = None
    evidence_dialog_ids: list[str] = Field(default_factory=list)
    evidence: list[RecommendationEvidence] = Field(default_factory=list)
    status: RecommendationStatus = "open"
    review_comment: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AnalysisKpiSummary(BaseModel):
    intervention_rate: float = Field(..., ge=0, le=1)
    tool_error_rate: float = Field(..., ge=0, le=1)
    tool_argument_mismatch_rate: float = Field(..., ge=0, le=1)
    topic_count: int = Field(..., ge=0)
    recommendation_count: int = Field(..., ge=0)


class AnalysisReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    period_start: datetime
    period_end: datetime
    window_hours: int = Field(..., ge=24, le=168)
    analysis_as_of: datetime
    analyzer_version: str
    model_name: str
    summary: str
    kpis: AnalysisKpiSummary
    topics: list[TopicSummary] = Field(default_factory=list)
    top_failure_topics: list[str] = Field(default_factory=list)
    recommendation_count_by_category: dict[str, int] = Field(default_factory=dict)
    created_at: datetime


class AnalysisJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    status: JobStatus
    stage: str = Field(..., description="Текущий этап выполнения.")
    progress_pct: int = Field(..., ge=0, le=100)
    period_start: datetime
    period_end: datetime
    window_hours: int = Field(..., ge=24, le=168)
    only_with_manager: bool
    max_dialogs: int
    history_limit: int
    max_tokens_per_job: int
    max_llm_requests_per_job: int
    idempotency_key: str | None = None
    analysis_as_of: datetime | None = None
    error_message: str | None = None
    report_id: UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_by_user_id: UUID | None = None
    cancelled_by_user_id: UUID | None = None


class AnalysisDataEnvelope(BaseModel):
    data: Any


class AnalysisJobsListData(BaseModel):
    items: list[AnalysisJobRead]
    next_cursor: str | None = Field(default=None, description="Курсор для следующей страницы.")


class AnalysisJobsListResponse(BaseModel):
    data: AnalysisJobsListData


class AnalysisRecommendationsListData(BaseModel):
    items: list[AnalysisRecommendationRead]
    total: int
    limit: int
    offset: int


class AnalysisRecommendationsListResponse(BaseModel):
    data: AnalysisRecommendationsListData


class RecommendationReviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["accepted", "rejected"] = Field(..., description="Результат review.")
    review_comment: str | None = Field(default=None, max_length=2000, alias="reviewer_comment")


class AnalysisJobStartResponse(BaseModel):
    data: AnalysisJobRead


class AnalysisJobCancelResponse(BaseModel):
    data: AnalysisJobRead


class AnalysisRecommendationResponse(BaseModel):
    data: AnalysisRecommendationRead


class AnalysisReportMeta(BaseModel):
    job_id: UUID
    report_id: UUID
    period_start: datetime
    period_end: datetime
    window_hours: int = Field(..., ge=24, le=168)
    analysis_as_of: datetime
    analyzer_version: str
    model_name: str
    recommendation_count_by_category: dict[str, int] = Field(default_factory=dict)
    created_at: datetime


class AnalysisReportPayload(BaseModel):
    summary: str
    kpis: AnalysisKpiSummary
    topics: list[TopicSummary] = Field(default_factory=list)
    top_failure_topics: list[str] = Field(default_factory=list)
    meta: AnalysisReportMeta


class AnalysisReportResponse(BaseModel):
    data: AnalysisReportPayload


class AnalyzerTopicResult(BaseModel):
    name: str
    dialogs_count: int = Field(..., ge=0)
    share: float = Field(..., ge=0, le=1)
    health: Literal["good", "warning", "critical"] = "warning"


class AnalyzerRecommendationResult(BaseModel):
    category: RecommendationCategory
    priority: RecommendationPriority
    confidence: float = Field(..., ge=0, le=1)
    title: str
    reasoning: str
    suggestion: str
    impact: str | None = None
    evidence_dialog_ids: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class AnalyzerOutput(BaseModel):
    summary: str
    topics: list[AnalyzerTopicResult] = Field(default_factory=list)
    recommendations: list[AnalyzerRecommendationResult] = Field(default_factory=list)
