from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.db.session import get_db
from app.schemas.analytics import (
    AnalyticsBreakdownDimension,
    AnalyticsBreakdownResponse,
    AnalyticsCommoditiesTableResponse,
    AnalyticsCommoditiesTableSortBy,
    AnalyticsFiltersMetaResponse,
    AnalyticsOverviewResponse,
    AnalyticsRevenueBasis,
    AnalyticsServicesTableResponse,
    AnalyticsServicesTableSortBy,
    AnalyticsSortOrder,
    AnalyticsTimeGroup,
    AnalyticsTimeseriesResponse,
)
from app.schemas.auth import AuthContext
from app.services.analytics import (
    AgentAnalyticsService,
    build_analytics_period,
    default_analytics_dates,
)

router = APIRouter()

_MAX_PERIOD_DAYS = 366
_DEFAULT_TIMEZONE = "UTC"


def _resolve_timezone_for_defaults(timezone_name: str | None, fallback_timezone: str | None) -> ZoneInfo:
    candidates = [timezone_name, fallback_timezone, _DEFAULT_TIMEZONE]
    for candidate in candidates:
        normalized = (candidate or "").strip()
        if not normalized:
            continue
        try:
            return ZoneInfo(normalized)
        except ZoneInfoNotFoundError:
            continue
    return ZoneInfo(_DEFAULT_TIMEZONE)


def _parse_client_tags(query_tags: list[str], csv_tags: str | None) -> list[str]:
    chunks: list[str] = []
    chunks.extend(query_tags)
    if csv_tags:
        chunks.append(csv_tags)

    values: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        for raw_item in str(chunk).split(","):
            normalized = raw_item.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            values.append(normalized)
    return values


def _resolve_period(
    *,
    date_from: date | None,
    date_to: date | None,
    timezone_name: str | None,
    fallback_timezone: str | None,
):
    if (date_from is None) ^ (date_to is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Передайте оба параметра date_from и date_to или не передавайте их вовсе",
        )

    if date_from is None or date_to is None:
        default_tz = _resolve_timezone_for_defaults(timezone_name, fallback_timezone)
        now_local = datetime.now(default_tz)
        date_from, date_to = default_analytics_dates(now_local)

    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_to не может быть раньше date_from",
        )

    if (date_to - date_from) > timedelta(days=_MAX_PERIOD_DAYS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Слишком большой период, максимум {_MAX_PERIOD_DAYS} дней",
        )

    return build_analytics_period(
        date_from=date_from,
        date_to=date_to,
        timezone_name=timezone_name,
        fallback_timezone=fallback_timezone,
    )


@router.get("/analytics/overview", response_model=AnalyticsOverviewResponse)
async def get_agent_analytics_overview(
    agent_id: UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    timezone: str | None = Query(default=None),
    revenue_basis: AnalyticsRevenueBasis = Query(
        default="all",
        description="all — все типы; clinical — service-sell, commodity-sell, alternative-payment, certificate-sell (как «Сумма продаж» в отчёте по услугам SQNS).",
    ),
    channel: str | None = Query(default=None),
    client_tags: list[str] = Query(default_factory=list, alias="client_tags"),
    tags: str | None = Query(default=None, alias="tags"),
    payment_methods: list[str] = Query(default_factory=list, alias="payment_methods"),
    revenue_categories: list[str] = Query(
        default_factory=list,
        alias="revenue_categories",
        description="services, commodities — фильтр по типу оплаты SQNS (услуги / товары). Пусто — все.",
    ),
    resource_external_id: int | None = Query(
        default=None,
        description="Внешний ID сотрудника (SQNS resource); только визиты этого специалиста.",
    ),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("analytics:view")),
) -> AnalyticsOverviewResponse:
    agent = await get_agent_or_404(agent_id, db, user)
    period = _resolve_period(
        date_from=date_from,
        date_to=date_to,
        timezone_name=timezone,
        fallback_timezone=agent.timezone,
    )
    service = AgentAnalyticsService(db, agent)
    return await service.get_overview(
        period=period,
        channel=channel,
        client_tags=_parse_client_tags(client_tags, tags),
        revenue_basis=revenue_basis,
        payment_methods=payment_methods or None,
        revenue_categories=revenue_categories or None,
        resource_external_id=resource_external_id,
    )


@router.get("/analytics/timeseries", response_model=AnalyticsTimeseriesResponse)
async def get_agent_analytics_timeseries(
    agent_id: UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    timezone: str | None = Query(default=None),
    revenue_basis: AnalyticsRevenueBasis = Query(default="all"),
    group_by: AnalyticsTimeGroup = Query(default="day"),
    channel: str | None = Query(default=None),
    client_tags: list[str] = Query(default_factory=list, alias="client_tags"),
    tags: str | None = Query(default=None, alias="tags"),
    payment_methods: list[str] = Query(default_factory=list, alias="payment_methods"),
    revenue_categories: list[str] = Query(default_factory=list, alias="revenue_categories"),
    resource_external_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("analytics:view")),
) -> AnalyticsTimeseriesResponse:
    agent = await get_agent_or_404(agent_id, db, user)
    period = _resolve_period(
        date_from=date_from,
        date_to=date_to,
        timezone_name=timezone,
        fallback_timezone=agent.timezone,
    )
    service = AgentAnalyticsService(db, agent)
    return await service.get_timeseries(
        period=period,
        group_by=group_by,
        channel=channel,
        client_tags=_parse_client_tags(client_tags, tags),
        revenue_basis=revenue_basis,
        payment_methods=payment_methods or None,
        revenue_categories=revenue_categories or None,
        resource_external_id=resource_external_id,
    )


@router.get("/analytics/breakdown", response_model=AnalyticsBreakdownResponse)
async def get_agent_analytics_breakdown(
    agent_id: UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    timezone: str | None = Query(default=None),
    dimension: AnalyticsBreakdownDimension = Query(default="channel"),
    channel: str | None = Query(default=None),
    client_tags: list[str] = Query(default_factory=list, alias="client_tags"),
    tags: str | None = Query(default=None, alias="tags"),
    limit: int = Query(default=10, ge=1, le=100),
    resource_external_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("analytics:view")),
) -> AnalyticsBreakdownResponse:
    agent = await get_agent_or_404(agent_id, db, user)
    period = _resolve_period(
        date_from=date_from,
        date_to=date_to,
        timezone_name=timezone,
        fallback_timezone=agent.timezone,
    )
    service = AgentAnalyticsService(db, agent)
    return await service.get_breakdown(
        period=period,
        dimension=dimension,
        channel=channel,
        client_tags=_parse_client_tags(client_tags, tags),
        limit=limit,
        resource_external_id=resource_external_id,
    )


@router.get("/analytics/filters-meta", response_model=AnalyticsFiltersMetaResponse)
async def get_agent_analytics_filters_meta(
    agent_id: UUID,
    timezone: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("analytics:view")),
) -> AnalyticsFiltersMetaResponse:
    agent = await get_agent_or_404(agent_id, db, user)
    service = AgentAnalyticsService(db, agent)
    return await service.get_filters_meta(timezone_name=timezone)


@router.get("/analytics/services-table", response_model=AnalyticsServicesTableResponse)
async def get_agent_analytics_services_table(
    agent_id: UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    timezone: str | None = Query(default=None),
    revenue_basis: AnalyticsRevenueBasis = Query(default="all"),
    channel: str | None = Query(default=None),
    resource_external_id: int | None = Query(default=None),
    client_tags: list[str] = Query(default_factory=list, alias="client_tags"),
    tags: str | None = Query(default=None, alias="tags"),
    payment_methods: list[str] = Query(default_factory=list, alias="payment_methods"),
    revenue_categories: list[str] = Query(default_factory=list, alias="revenue_categories"),
    sort_by: AnalyticsServicesTableSortBy = Query(default="bookings_total"),
    sort_order: AnalyticsSortOrder = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("analytics:view")),
) -> AnalyticsServicesTableResponse:
    agent = await get_agent_or_404(agent_id, db, user)
    period = _resolve_period(
        date_from=date_from,
        date_to=date_to,
        timezone_name=timezone,
        fallback_timezone=agent.timezone,
    )
    service = AgentAnalyticsService(db, agent)
    return await service.get_services_table(
        period=period,
        channel=channel,
        client_tags=_parse_client_tags(client_tags, tags),
        resource_external_id=resource_external_id,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
        revenue_basis=revenue_basis,
        payment_methods=payment_methods or None,
        revenue_categories=revenue_categories or None,
    )


@router.get("/analytics/commodities-table", response_model=AnalyticsCommoditiesTableResponse)
async def get_agent_analytics_commodities_table(
    agent_id: UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    timezone: str | None = Query(default=None),
    revenue_basis: AnalyticsRevenueBasis = Query(default="all"),
    channel: str | None = Query(default=None),
    resource_external_id: int | None = Query(default=None),
    client_tags: list[str] = Query(default_factory=list, alias="client_tags"),
    tags: str | None = Query(default=None, alias="tags"),
    payment_methods: list[str] = Query(default_factory=list, alias="payment_methods"),
    revenue_categories: list[str] = Query(default_factory=list, alias="revenue_categories"),
    sort_by: AnalyticsCommoditiesTableSortBy = Query(default="bookings_total"),
    sort_order: AnalyticsSortOrder = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("analytics:view")),
) -> AnalyticsCommoditiesTableResponse:
    agent = await get_agent_or_404(agent_id, db, user)
    period = _resolve_period(
        date_from=date_from,
        date_to=date_to,
        timezone_name=timezone,
        fallback_timezone=agent.timezone,
    )
    service = AgentAnalyticsService(db, agent)
    return await service.get_commodities_table(
        period=period,
        channel=channel,
        client_tags=_parse_client_tags(client_tags, tags),
        resource_external_id=resource_external_id,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
        revenue_basis=revenue_basis,
        payment_methods=payment_methods or None,
        revenue_categories=revenue_categories or None,
    )
