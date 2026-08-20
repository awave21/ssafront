"""Pydantic schemas for analytics v2: staff/managers/bot health/insights/AI recommendations."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---------- shared ----------

class _PeriodMixin(BaseModel):
    period_start: datetime
    period_end: datetime
    timezone: str


# ---------- staff ----------

class StaffMember(BaseModel):
    resource_external_id: int
    full_name: str
    position: str | None = None
    is_fired: bool = False
    visits_total: int = 0
    arrived_total: int = 0
    no_show_total: int = 0
    no_show_pct: float = 0.0
    primary_total: int = 0
    primary_arrived: int = 0
    repeat_total: int = 0
    conversion_pct: float = Field(default=0.0, description="arrived / visits %")
    revenue_total: float = 0.0
    margin_total: float = 0.0
    avg_check: float = 0.0
    revenue_delta_pct: float | None = Field(default=None, description="vs previous period")
    visits_delta_pct: float | None = None


class StaffOverviewResponse(_PeriodMixin):
    items: list[StaffMember] = Field(default_factory=list)
    employees_total: int = 0


class StaffServiceLine(BaseModel):
    service_external_id: int | None
    service_name: str
    bookings_total: int
    arrived_total: int = 0
    no_show_total: int = 0
    primary_total: int = 0
    repeat_total: int = 0
    revenue_total: float
    avg_check: float = 0.0
    conversion_pct: float = 0.0
    no_show_pct: float = 0.0


class StaffClientLine(BaseModel):
    client_external_id: int
    full_name: str
    phone: str | None = None
    visits_total: int = 0
    arrived_total: int = 0
    no_show_total: int = 0
    primary_total: int = 0
    repeat_total: int = 0
    revenue_total: float = 0.0
    avg_check: float = 0.0
    last_visit_at: datetime | None = None


class StaffSparkPoint(BaseModel):
    bucket: str
    visits: int
    revenue: float


class StaffDetailResponse(_PeriodMixin):
    staff: StaffMember
    top_services: list[StaffServiceLine] = Field(default_factory=list)
    clients: list[StaffClientLine] = Field(default_factory=list)
    sparkline: list[StaffSparkPoint] = Field(default_factory=list)


# ---------- managers ----------

class ManagerStat(BaseModel):
    user_id: UUID | None = Field(default=None, description="users.id (если известно)")
    full_name: str
    email: str | None = None
    overrides_count: int = Field(default=0, description="число ручных вмешательств в чат")
    bot_disable_count: int = Field(default=0, description="отключения бота")
    dialogs_paused_count: int = 0
    avg_first_response_seconds: float | None = Field(default=None, description="медиана времени первого ответа")
    last_active_at: datetime | None = None


class ManagersOverviewResponse(_PeriodMixin):
    items: list[ManagerStat] = Field(default_factory=list)
    managers_total: int = 0
    overrides_total: int = 0
    bot_disable_total: int = 0


class ManagerOverrideEvent(BaseModel):
    happened_at: datetime
    event_type: Literal["manager_message", "bot_disabled", "dialog_paused"]
    session_id: str | None = None
    user_id: UUID | None = None
    full_name: str | None = None
    text_preview: str | None = None


class ManagersTimelineResponse(_PeriodMixin):
    events: list[ManagerOverrideEvent] = Field(default_factory=list)


# ---------- bot health ----------

class BotRunsKpi(BaseModel):
    runs_total: int = 0
    success_pct: float = 0.0
    failed_total: int = 0
    avg_duration_ms: float = 0.0
    prompt_tokens_total: int = 0
    completion_tokens_total: int = 0
    cost_usd_total: float = 0.0
    cost_rub_total: float = 0.0


class BotToolStat(BaseModel):
    tool_name: str
    calls_total: int
    error_count: int
    error_pct: float
    p50_ms: float | None = None
    p95_ms: float | None = None
    avg_ms: float | None = None


class BotDialogQuality(BaseModel):
    dialogs_total: int = 0
    dialogs_with_manager: int = 0
    dialogs_paused: int = 0
    dialogs_disabled: int = 0
    autonomy_pct: float = Field(default=0.0, description="доля диалогов без вмешательства менеджера")
    avg_messages_per_dialog: float = 0.0


class BotBudget(BaseModel):
    initial_balance_usd: float = 0.0
    spent_usd: float = 0.0
    remaining_usd: float = 0.0
    spent_pct: float = 0.0
    burn_rate_usd_per_day: float = 0.0
    days_to_zero: float | None = None
    last_14d_usd: float = 0.0


class BotHealthResponse(_PeriodMixin):
    runs: BotRunsKpi
    tools: list[BotToolStat] = Field(default_factory=list)
    dialogs: BotDialogQuality
    budget: BotBudget


# ---------- funnel ----------

class FunnelStage(BaseModel):
    key: str
    label: str
    value: int


class FunnelResponse(_PeriodMixin):
    stages: list[FunnelStage] = Field(default_factory=list)


# ---------- insights ----------

InsightSeverity = Literal["info", "warning", "critical"]
InsightCategory = Literal["staff", "manager", "bot", "budget", "dialog", "organization"]


class Insight(BaseModel):
    code: str = Field(description="machine code, e.g. staff_conversion_drop")
    severity: InsightSeverity
    category: InsightCategory
    title: str
    body: str
    metric_value: float | None = None
    metric_label: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    action_url: str | None = None
    action_tab: str | None = Field(default=None, description="tab key для перехода в UI")


class InsightsResponse(_PeriodMixin):
    items: list[Insight] = Field(default_factory=list)


# ---------- AI recommendations ----------

AiRecommendationPriority = Literal["high", "medium", "low"]
AiEffortLevel = Literal["low", "medium", "high"]
AiConfidenceLevel = Literal["low", "medium", "high"]
AiPeriodVerdict = Literal["positive", "neutral", "negative"]


class AiRecommendation(BaseModel):
    priority: AiRecommendationPriority
    title: str = Field(description="до 80 символов")
    body: str = Field(description="2-4 предложения, что и почему сделать")
    root_cause: str | None = Field(default=None, description="короткая гипотеза откуда проблема")
    expected_impact_rub: int | None = Field(default=None, description="ожидаемый годовой эффект в рублях")
    effort: AiEffortLevel | None = Field(default=None, description="трудозатраты руководителя")
    confidence: AiConfidenceLevel | None = Field(default=None, description="уверенность аналитика в рекомендации")
    risk_if_ignored: str | None = Field(default=None, description="что произойдёт если не сделать")
    target_entity: str | None = Field(default=None, description="на кого направлено: имя сотрудника, бот, и т.п.")
    target_tab: str | None = Field(default=None, description="staff|managers|bot|catalog|overview")


class AiRecommendationsPayload(BaseModel):
    summary: str = Field(description="2-3 предложения executive summary за период")
    headline_metric: str | None = Field(default=None, description="одна цифра-зацепка, напр. «маржа 38%» или «no-show 15%»")
    period_verdict: AiPeriodVerdict | None = Field(default=None, description="общая оценка периода")
    wins: list[str] = Field(default_factory=list, description="0-3 коротких тезиса что работает хорошо")
    risks: list[str] = Field(default_factory=list, description="0-3 коротких тезиса что горит")
    recommendations: list[AiRecommendation] = Field(default_factory=list)


class AiRecommendationsResponse(_PeriodMixin):
    payload: AiRecommendationsPayload
    generated_at: datetime
    cached: bool = False
    model: str | None = None
