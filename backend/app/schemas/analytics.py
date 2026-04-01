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

AnalyticsCommoditiesTableSortBy = Literal[
    "commodity_name",
    "bookings_total",
    "arrived_total",
    "primary_total",
    "primary_arrived_total",
    "repeat_total",
    "revenue_total",
    "avg_check",
]

# all — все типы платежей из API (как полная касса).
# clinical — услуги, товары, сертификаты (как итог «Сумма продаж» в отчёте по услугам SQNS), без прочих доходов.
AnalyticsRevenueBasis = Literal["all", "clinical"]


class AnalyticsOverviewResponse(BaseModel):
    visits_total: int = Field(default=0, ge=0)
    arrived_total: int = Field(default=0, ge=0)
    primary_visits: int = Field(default=0, ge=0)
    primary_arrived: int = Field(default=0, ge=0)
    conversion_primary_arrived_pct: float = Field(default=0, ge=0, le=100)
    arrived_primary: int = Field(default=0, ge=0)
    repeat_total: int = Field(default=0, ge=0)
    repeat_arrived: int = Field(default=0, ge=0)
    conversion_repeat_arrived_pct: float = Field(default=0, ge=0, le=100)
    repeat_revenue: float = Field(default=0)
    primary_revenue: float = Field(default=0)
    primary_avg_check: float = Field(
        default=0,
        ge=0,
        description="Средняя выручка на дошедшего первичного: primary_revenue / primary_arrived.",
    )
    repeat_avg_check: float = Field(
        default=0,
        ge=0,
        description="Средняя выручка на дошедшего повторного: repeat_revenue / repeat_arrived.",
    )
    bookings_from_primary: int = Field(default=0, ge=0)
    conversion_arrived_to_booked_pct: float = Field(default=0, ge=0, le=100)
    avg_check: float = Field(default=0, ge=0)
    revenue_total: float = Field(
        default=0,
        ge=0,
        description="Сумма платежей с датой оплаты в выбранном периоде (payment_date, границы как у period_start/period_end).",
    )
    payments_total: int = Field(
        default=0,
        ge=0,
        description="Число платежей с суммой и датой оплаты в выбранном периоде.",
    )
    revenue_basis: AnalyticsRevenueBasis = Field(
        default="all",
        description="База выручки: all — все типы; clinical — услуги, товары, сертификаты/alternative-payment (как итог отчёта по услугам SQNS), без other-income.",
    )
    period_start: datetime
    period_end: datetime
    timezone: str
    last_sync_at: datetime | None = None


class AnalyticsTimeseriesPoint(BaseModel):
    bucket: str = Field(..., description="Ключ бакета (YYYY-MM-DD)")
    label: str = Field(..., description="Короткая подпись для графика")
    visits_total: int = Field(default=0, ge=0)
    arrived_total: int = Field(default=0, ge=0)
    primary_visits: int = Field(default=0, ge=0)
    primary_arrived: int = Field(default=0, ge=0)
    revenue_total: float = Field(
        default=0,
        ge=0,
        description="Сумма платежей по дате оплаты в бакете (локальная таймзона периода).",
    )


class AnalyticsTimeseriesResponse(BaseModel):
    group_by: AnalyticsTimeGroup
    timezone: str
    period_start: datetime
    period_end: datetime
    revenue_basis: AnalyticsRevenueBasis = "all"
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
    revenue_basis: AnalyticsRevenueBasis = "all"
    last_sync_at: datetime | None = None
    resource_external_id: int | None = None
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: AnalyticsServicesTableSortBy = "bookings_total"
    sort_order: AnalyticsSortOrder = "desc"
    totals: AnalyticsServicesTableTotals
    items: list[AnalyticsServiceTableItem] = Field(default_factory=list)


class AnalyticsCommodityTableItem(BaseModel):
    commodity_key: str
    commodity_external_id: int | None = None
    commodity_name: str
    commodity_category: str | None = None
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


class AnalyticsCommoditiesTableTotals(BaseModel):
    commodities_total: int = Field(default=0, ge=0)
    bookings_total: int = Field(default=0, ge=0)
    arrived_total: int = Field(default=0, ge=0)
    primary_total: int = Field(default=0, ge=0)
    primary_arrived_total: int = Field(default=0, ge=0)
    repeat_total: int = Field(default=0, ge=0)
    repeat_arrived_total: int = Field(default=0, ge=0)
    revenue_total: float = Field(default=0, ge=0)
    payments_total: int = Field(default=0, ge=0)
    avg_check: float = Field(default=0, ge=0)


class AnalyticsCommoditiesTableResponse(BaseModel):
    timezone: str
    period_start: datetime
    period_end: datetime
    revenue_basis: AnalyticsRevenueBasis = "all"
    last_sync_at: datetime | None = None
    resource_external_id: int | None = None
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: AnalyticsCommoditiesTableSortBy = "bookings_total"
    sort_order: AnalyticsSortOrder = "desc"
    totals: AnalyticsCommoditiesTableTotals
    items: list[AnalyticsCommodityTableItem] = Field(default_factory=list)
