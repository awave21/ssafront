from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


AnalyticsTimeGroup = Literal["day", "week", "month"]
AnalyticsBreakdownDimension = Literal["channel", "tag", "client_type"]
AnalyticsSortOrder = Literal["asc", "desc"]
AnalyticsServicesTableSortBy = Literal[
    "service_name",
    "bookings_total",
    "arrived_total",
    "primary_total",
    "primary_arrived_total",
    "repeat_total",
    "revenue_total",
    "avg_check",
]


class AnalyticsOverviewResponse(BaseModel):
    visits_total: int = Field(default=0, ge=0)
    arrived_total: int = Field(default=0, ge=0)
    arrived_primary: int = Field(default=0, ge=0)
    repeat_total: int = Field(default=0, ge=0)
    bookings_from_primary: int = Field(default=0, ge=0)
    bookings_from_existing_patients: int = Field(default=0, ge=0)
    conversion_arrived_to_booked_pct: float = Field(default=0, ge=0, le=100)
    avg_check: float = Field(default=0, ge=0)
    revenue_total: float = Field(default=0)
    payments_total: int = Field(default=0, ge=0)
    period_start: datetime
    period_end: datetime
    timezone: str
    last_sync_at: datetime | None = None


class AnalyticsTimeseriesPoint(BaseModel):
    bucket: str = Field(..., description="Ключ бакета (YYYY-MM-DD)")
    label: str = Field(..., description="Короткая подпись для графика")
    visits_total: int = Field(default=0, ge=0)
    arrived_total: int = Field(default=0, ge=0)
    revenue_total: float = Field(default=0)


class AnalyticsTimeseriesResponse(BaseModel):
    group_by: AnalyticsTimeGroup
    timezone: str
    period_start: datetime
    period_end: datetime
    points: list[AnalyticsTimeseriesPoint] = Field(default_factory=list)


class AnalyticsBreakdownItem(BaseModel):
    key: str
    label: str
    count: int = Field(default=0, ge=0)
    share: float = Field(default=0, ge=0, le=1)


class AnalyticsBreakdownResponse(BaseModel):
    dimension: AnalyticsBreakdownDimension
    total: int = Field(default=0, ge=0)
    items: list[AnalyticsBreakdownItem] = Field(default_factory=list)
    period_start: datetime
    period_end: datetime
    timezone: str


class AnalyticsFilterOption(BaseModel):
    value: str
    label: str


class AnalyticsFiltersMetaResponse(BaseModel):
    timezone: str
    default_period_days: int = Field(default=30, ge=1, le=365)
    min_date: date | None = None
    max_date: date | None = None
    last_sync_at: datetime | None = None
    available_channels: list[AnalyticsFilterOption] = Field(default_factory=list)
    available_tags: list[AnalyticsFilterOption] = Field(default_factory=list)
    phase2_backlog: list[str] = Field(default_factory=list)


class AnalyticsServiceTableItem(BaseModel):
    service_key: str
    service_external_id: int | None = None
    service_name: str
    service_category: str | None = None
    bookings_total: int = Field(default=0, ge=0)
    arrived_total: int = Field(default=0, ge=0)
    primary_total: int = Field(default=0, ge=0)
    primary_arrived_total: int = Field(default=0, ge=0)
    repeat_total: int = Field(default=0, ge=0)
    repeat_arrived_total: int = Field(default=0, ge=0)
    revenue_total: float = Field(default=0, ge=0)
    payments_total: int = Field(default=0, ge=0)
    avg_check: float = Field(default=0, ge=0)
    share_bookings: float = Field(default=0, ge=0, le=1)


class AnalyticsServicesTableTotals(BaseModel):
    services_total: int = Field(default=0, ge=0)
    bookings_total: int = Field(default=0, ge=0)
    arrived_total: int = Field(default=0, ge=0)
    primary_total: int = Field(default=0, ge=0)
    primary_arrived_total: int = Field(default=0, ge=0)
    repeat_total: int = Field(default=0, ge=0)
    repeat_arrived_total: int = Field(default=0, ge=0)
    revenue_total: float = Field(default=0, ge=0)
    payments_total: int = Field(default=0, ge=0)
    avg_check: float = Field(default=0, ge=0)


class AnalyticsServicesTableResponse(BaseModel):
    timezone: str
    period_start: datetime
    period_end: datetime
    last_sync_at: datetime | None = None
    resource_external_id: int | None = None
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: AnalyticsServicesTableSortBy = "bookings_total"
    sort_order: AnalyticsSortOrder = "desc"
    totals: AnalyticsServicesTableTotals
    items: list[AnalyticsServiceTableItem] = Field(default_factory=list)
