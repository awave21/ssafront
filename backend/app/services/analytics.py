from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.channel import AgentChannel, Channel
from app.db.models.sqns_service import (
    SqnsClientRecord,
    SqnsCommodity,
    SqnsPayment,
    SqnsService,
    SqnsVisit,
)
from app.services.sqns.visit_arrival import is_sqns_visit_arrived
from app.schemas.analytics import (
    AnalyticsBreakdownDimension,
    AnalyticsBreakdownItem,
    AnalyticsBreakdownResponse,
    AnalyticsCommoditiesTableResponse,
    AnalyticsCommoditiesTableSortBy,
    AnalyticsCommoditiesTableTotals,
    AnalyticsCommodityTableItem,
    AnalyticsFilterOption,
    AnalyticsFiltersMetaResponse,
    AnalyticsOverviewResponse,
    AnalyticsRevenueBasis,
    AnalyticsServiceTableItem,
    AnalyticsServicesTableResponse,
    AnalyticsServicesTableSortBy,
    AnalyticsServicesTableTotals,
    AnalyticsSortOrder,
    AnalyticsTimeGroup,
    AnalyticsTimeseriesPoint,
    AnalyticsTimeseriesResponse,
)


_DEFAULT_TIMEZONE = "UTC"
_DEFAULT_PERIOD_DAYS = 30
_MAX_CHANNEL_SCAN_ROWS = 5000
_MAX_TAG_OPTIONS = 300

# Как в отчёте по визитам/услугам SQNS: услуги, товары, оплата сертификатом и продажа сертификатов.
# Без «прочих доходов» (other-income) — они обычно не входят в эту таблицу.
_CLINICAL_REVENUE_HANDLES: frozenset[str] = frozenset(
    {
        "service-sell",
        "commodity-sell",
        "alternative-payment",
        "certificate-sell",
    }
)

# Фильтры «Услуги» / «Товары» (paymentTypeHandle в SQNS).
_REVENUE_CATEGORY_HANDLES: dict[str, frozenset[str]] = {
    "services": frozenset({"service-sell", "alternative-payment", "certificate-sell"}),
    "commodities": frozenset({"commodity-sell"}),
}


def resolve_revenue_category_handles(categories: list[str] | None) -> frozenset[str] | None:
    """Объединение handles для выбранных категорий; None — без фильтра по типу оплаты."""
    if not categories:
        return None
    out: set[str] = set()
    for item in categories:
        key = _normalize_text(item)
        if key in _REVENUE_CATEGORY_HANDLES:
            out.update(_REVENUE_CATEGORY_HANDLES[key])
    return frozenset(out) if out else None


_PHASE2_BACKLOG = [
    "Возвращаемость за 3 месяца",
    "Возвращаемость за 6 месяцев",
    "Возвращаемость за 12 месяцев",
    "Причины отказа из списка в МИС",
]

_CHANNEL_LABELS = {
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "max": "MAX",
    "phone": "Телефон",
    "website": "Сайт",
    "online": "Онлайн",
    "offline": "Оффлайн",
    "other": "Прочее",
}


@dataclass(frozen=True)
class AnalyticsPeriod:
    date_from: date
    date_to: date
    timezone_name: str
    tz: ZoneInfo
    start_local: datetime
    end_local_exclusive: datetime
    start_utc: datetime
    end_utc: datetime


@dataclass
class VisitContext:
    visit: SqnsVisit
    client: SqnsClientRecord | None
    channel: str
    client_tags: set[str]
    is_primary: bool
    is_repeat: bool
    is_arrived: bool


@dataclass
class AnalyticsDataset:
    visits: list[SqnsVisit]
    payments: list[SqnsPayment]
    clients_by_external_id: dict[int, SqnsClientRecord]


@dataclass
class AnalyticsView:
    visit_contexts: list[VisitContext]
    payments: list[SqnsPayment]


@dataclass
class VisitServiceRef:
    service_key: str
    service_external_id: int | None
    service_name: str | None


@dataclass
class ServiceMetricsAccumulator:
    service_key: str
    service_external_id: int | None
    service_name: str
    service_category: str | None = None
    bookings_total: int = 0
    arrived_total: int = 0
    primary_total: int = 0
    primary_arrived_total: int = 0
    repeat_total: int = 0
    repeat_arrived_total: int = 0
    revenue_total: Decimal = Decimal("0")
    payments_total: int = 0
    avg_check: float = 0.0


@dataclass
class CommodityMetricsAccumulator:
    commodity_key: str
    commodity_external_id: int | None
    commodity_name: str
    commodity_category: str | None = None
    bookings_total: int = 0
    arrived_total: int = 0
    primary_total: int = 0
    primary_arrived_total: int = 0
    repeat_total: int = 0
    repeat_arrived_total: int = 0
    revenue_total: Decimal = Decimal("0")
    payments_total: int = 0
    avg_check: float = 0.0


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _read_nested(payload: dict[str, Any] | None, paths: Iterable[tuple[str, ...]]) -> Any:
    if not isinstance(payload, dict):
        return None
    for path in paths:
        current: Any = payload
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if current not in (None, ""):
                return current
    return None


def _normalize_channel(value: str | None) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        return "other"
    if "telegram" in normalized or normalized in {"tg"}:
        return "telegram"
    if "whatsapp" in normalized or normalized in {"wa", "wappi"}:
        return "whatsapp"
    if normalized == "max" or " max" in normalized or normalized.startswith("max_"):
        return "max"
    if normalized in {"phone", "call", "телефон", "звонок"}:
        return "phone"
    if normalized in {"site", "web", "website", "сайт", "landing"}:
        return "website"
    if normalized in {"online", "онлайн"}:
        return "online"
    if normalized in {"offline", "оффлайн"}:
        return "offline"
    return normalized


def _channel_label(channel_key: str) -> str:
    return _CHANNEL_LABELS.get(channel_key, channel_key.capitalize())


def _extract_visit_channel(visit: SqnsVisit) -> str:
    raw = visit.raw_data if isinstance(visit.raw_data, dict) else None
    if raw is None:
        return "other"

    direct_value = _read_nested(
        raw,
        (
            ("channel",),
            ("source",),
            ("platform",),
            ("communicationChannel",),
            ("communication_channel",),
            ("utm", "source"),
            ("utm", "channel"),
            ("visit", "channel"),
            ("visit", "source"),
            ("appointment", "channel"),
            ("appointment", "source"),
            ("client", "channel"),
        ),
    )
    if direct_value not in (None, ""):
        return _normalize_channel(str(direct_value))

    if isinstance(raw.get("online"), bool):
        return "online" if bool(raw["online"]) else "offline"

    return "other"


def _parse_intish(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _service_key(service_external_id: int | None, service_name: str | None) -> str:
    if service_external_id is not None:
        return f"id:{service_external_id}"
    normalized_name = _normalize_text(service_name)
    if normalized_name:
        return f"name:{normalized_name}"
    return "unknown"


def _extract_visit_service_refs(visit: SqnsVisit) -> list[VisitServiceRef]:
    raw = visit.raw_data if isinstance(visit.raw_data, dict) else None
    if raw is None:
        return [VisitServiceRef(service_key="unknown", service_external_id=None, service_name="Не определено")]

    service_refs: list[VisitServiceRef] = []

    direct_service_id = _parse_intish(
        _read_nested(
            raw,
            (
                ("serviceId",),
                ("service_id",),
                ("service", "id"),
                ("visit", "serviceId"),
                ("visit", "service_id"),
                ("visit", "service", "id"),
                ("appointment", "serviceId"),
                ("appointment", "service_id"),
                ("appointment", "service", "id"),
            ),
        )
    )
    direct_service_name_value = _read_nested(
        raw,
        (
            ("serviceName",),
            ("service_name",),
            ("service", "name"),
            ("visit", "serviceName"),
            ("visit", "service_name"),
            ("visit", "service", "name"),
            ("appointment", "serviceName"),
            ("appointment", "service_name"),
            ("appointment", "service", "name"),
        ),
    )
    direct_service_name = str(direct_service_name_value).strip() if direct_service_name_value is not None else None
    if direct_service_id is not None or (direct_service_name and direct_service_name.strip()):
        service_refs.append(
            VisitServiceRef(
                service_key=_service_key(direct_service_id, direct_service_name),
                service_external_id=direct_service_id,
                service_name=direct_service_name.strip() if direct_service_name else None,
            )
        )

    services_payload = _read_nested(
        raw,
        (
            ("services",),
            ("visit", "services"),
            ("appointment", "services"),
            ("visit", "appointment", "services"),
        ),
    )
    if isinstance(services_payload, list):
        for item in services_payload:
            if not isinstance(item, dict):
                continue
            item_service_id = _parse_intish(
                item.get("id")
                or item.get("serviceId")
                or item.get("service_id")
                or item.get("externalId")
                or item.get("external_id")
            )
            item_name_raw = item.get("name") or item.get("title") or item.get("serviceName") or item.get("service_name")
            item_name = str(item_name_raw).strip() if item_name_raw is not None else None
            service_refs.append(
                VisitServiceRef(
                    service_key=_service_key(item_service_id, item_name),
                    service_external_id=item_service_id,
                    service_name=item_name,
                )
            )

    deduplicated_refs: list[VisitServiceRef] = []
    seen_keys: set[str] = set()
    for item in service_refs:
        if item.service_key in seen_keys:
            continue
        seen_keys.add(item.service_key)
        deduplicated_refs.append(item)

    if not deduplicated_refs:
        return [VisitServiceRef(service_key="unknown", service_external_id=None, service_name="Не определено")]
    return deduplicated_refs


def _visit_item_pay_sums(raw: dict | None, key: str) -> dict[str, Decimal]:
    """Return {_service_key(id, name): paySum} for items in raw_data[key] (services or commodities).

    SQNS uses `amount` for quantity and `paySum` for the monetary contribution.
    We build the same key as _extract_visit_service_refs/_extract_commodity_refs so the maps align.
    """
    result: dict[str, Decimal] = {}
    if not isinstance(raw, dict):
        return result
    items = raw.get(key)
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict):
            continue
        if key == "commodities":
            raw_id = (
                item.get("id")
                or item.get("commodityId")
                or item.get("commodity_id")
                or item.get("productId")
                or item.get("product_id")
                or item.get("serviceId")
                or item.get("service_id")
                or item.get("externalId")
                or item.get("external_id")
            )
        else:
            raw_id = (
                item.get("id")
                or item.get("serviceId")
                or item.get("service_id")
                or item.get("externalId")
                or item.get("external_id")
            )
        item_id = _parse_intish(raw_id)
        name_raw = (
            item.get("name")
            or item.get("title")
            or item.get("serviceName")
            or item.get("service_name")
            or item.get("commodityName")
            or item.get("commodity_name")
        )
        item_name = str(name_raw).strip() if name_raw is not None else None
        k = _service_key(item_id, item_name)
        try:
            pay_sum = Decimal(str(item.get("paySum") or 0))
        except Exception:
            pay_sum = Decimal("0")
        result[k] = result.get(k, Decimal("0")) + pay_sum
    return result


def _visit_total_cost(raw: dict | None) -> Decimal:
    if not isinstance(raw, dict):
        return Decimal("0")
    try:
        return Decimal(str(raw.get("totalCost") or 0))
    except Exception:
        return Decimal("0")


def _visit_commodity_unique_entries(raw: dict | None) -> list[tuple[str, int | None, str | None]]:
    """Уникальные товары визита из raw_data (ключи совпадают с _visit_item_pay_sums(raw, 'commodities')).

    Не зависит от sqns_visit_commodity_lines — после переподключения SQNS визиты уже есть в БД с raw_data,
    а строки junction-таблицы могут быть пустыми до полного ресинка.
    """
    out: list[tuple[str, int | None, str | None]] = []
    seen: set[str] = set()
    if not isinstance(raw, dict):
        return out
    items = raw.get("commodities")
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_id = (
            item.get("id")
            or item.get("commodityId")
            or item.get("commodity_id")
            or item.get("productId")
            or item.get("product_id")
            or item.get("serviceId")
            or item.get("service_id")
            or item.get("externalId")
            or item.get("external_id")
        )
        item_id = _parse_intish(raw_id)
        name_raw = (
            item.get("name")
            or item.get("title")
            or item.get("serviceName")
            or item.get("service_name")
            or item.get("commodityName")
            or item.get("commodity_name")
        )
        item_name = str(name_raw).strip() if name_raw is not None else None
        k = _service_key(item_id, item_name)
        if k in seen:
            continue
        seen.add(k)
        out.append((k, item_id, item_name))
    return out


def _extract_client_tags(client: SqnsClientRecord | None) -> set[str]:
    if client is None:
        return set()
    raw_tags = client.tags if isinstance(client.tags, list) else []
    result: set[str] = set()
    for item in raw_tags:
        if isinstance(item, str):
            normalized = _normalize_text(item)
            if normalized:
                result.add(normalized)
            continue
        if isinstance(item, dict):
            candidate = item.get("name") or item.get("tag") or item.get("value")
            normalized = _normalize_text(candidate)
            if normalized:
                result.add(normalized)
    return result


def _to_utc_datetime(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("UTC"))


def _classify_visit_type(*, visit: SqnsVisit) -> tuple[bool, bool]:
    """Первичный/повторный только по флагу is_primary_visit из SQNS (без эвристик по периоду и raw_data)."""
    if visit.is_primary_visit is True:
        return True, False
    if visit.is_primary_visit is False:
        return False, True
    return False, False


def _is_arrived_visit(visit: SqnsVisit) -> bool:
    return is_sqns_visit_arrived(visit)


def _to_local_datetime(dt: datetime | None, tz: ZoneInfo) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    return dt.astimezone(tz)


def _round_money(value: Decimal) -> float:
    return round(float(value), 2)


def _payment_datetime_to_utc_second(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("UTC")).replace(microsecond=0)


def _payment_revenue_dedupe_key(payment: SqnsPayment) -> tuple[Any, ...]:
    """Ключ для схлопывания дублей одного фактического платежа в SQNS.

    В ответе API иногда приходят две записи с одним визитом, суммой, датой и типом,
    но разным clientId в payload — hash external_id разный, строки дублируются в БД.
    В отчётах SQNS такой платёж один; суммируя все строки, мы завышаем выручку.
    """
    visit = _normalize_text(payment.visit_external_id)
    if not visit:
        return ("orphan", payment.external_id)
    ts = _payment_datetime_to_utc_second(payment.payment_date)
    amt = payment.amount or Decimal("0")
    ptype = _normalize_text(payment.payment_type_handle) or _normalize_text(payment.payment_type_id) or ""
    return ("visit", visit, ts, str(amt), ptype)


def _dedupe_payments_for_revenue(payments: list[SqnsPayment]) -> list[SqnsPayment]:
    seen: set[tuple[Any, ...]] = set()
    out: list[SqnsPayment] = []
    for p in payments:
        key = _payment_revenue_dedupe_key(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _payment_allowed_for_revenue_basis(payment: SqnsPayment, basis: AnalyticsRevenueBasis) -> bool:
    if basis != "clinical":
        return True
    handle = _normalize_text(payment.payment_type_handle)
    if not handle:
        return False
    return handle in _CLINICAL_REVENUE_HANDLES


def _resolve_zoneinfo(timezone_name: str | None, fallback_timezone: str | None) -> tuple[str, ZoneInfo]:
    candidates = [timezone_name, fallback_timezone, _DEFAULT_TIMEZONE]
    for candidate in candidates:
        normalized = (candidate or "").strip()
        if not normalized:
            continue
        try:
            return normalized, ZoneInfo(normalized)
        except ZoneInfoNotFoundError:
            continue
    return _DEFAULT_TIMEZONE, ZoneInfo(_DEFAULT_TIMEZONE)


def build_analytics_period(
    *,
    date_from: date,
    date_to: date,
    timezone_name: str | None,
    fallback_timezone: str | None,
) -> AnalyticsPeriod:
    resolved_timezone, tz = _resolve_zoneinfo(timezone_name, fallback_timezone)
    start_local = datetime.combine(date_from, time.min, tzinfo=tz)
    end_local_exclusive = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz)
    start_utc = start_local.astimezone(ZoneInfo("UTC"))
    end_utc = end_local_exclusive.astimezone(ZoneInfo("UTC"))
    return AnalyticsPeriod(
        date_from=date_from,
        date_to=date_to,
        timezone_name=resolved_timezone,
        tz=tz,
        start_local=start_local,
        end_local_exclusive=end_local_exclusive,
        start_utc=start_utc,
        end_utc=end_utc,
    )


def default_analytics_dates(now_local: datetime | None = None) -> tuple[date, date]:
    anchor = now_local or datetime.now(ZoneInfo(_DEFAULT_TIMEZONE))
    end_date = anchor.date()
    start_date = end_date - timedelta(days=_DEFAULT_PERIOD_DAYS - 1)
    return start_date, end_date


class AgentAnalyticsService:
    def __init__(self, db: AsyncSession, agent: Agent):
        self.db = db
        self.agent = agent

    async def get_overview(
        self,
        *,
        period: AnalyticsPeriod,
        channel: str | None,
        client_tags: list[str],
        revenue_basis: AnalyticsRevenueBasis = "all",
        payment_methods: list[str] | None = None,
        revenue_categories: list[str] | None = None,
        resource_external_id: int | None = None,
    ) -> AnalyticsOverviewResponse:
        dataset = await self._load_dataset(period)
        view = self._build_view(
            dataset,
            period=period,
            channel=channel,
            client_tags=client_tags,
            revenue_basis=revenue_basis,
            payment_methods=payment_methods,
            revenue_categories=revenue_categories,
            resource_external_id=resource_external_id,
        )

        visits_total = len(view.visit_contexts)
        arrived_total = sum(1 for item in view.visit_contexts if item.is_arrived)
        primary_visits = sum(1 for item in view.visit_contexts if item.is_primary)
        primary_arrived = sum(1 for item in view.visit_contexts if item.is_arrived and item.is_primary)
        arrived_primary = primary_arrived
        repeat_total = sum(1 for item in view.visit_contexts if item.is_repeat)
        repeat_arrived = sum(1 for item in view.visit_contexts if item.is_arrived and item.is_repeat)
        bookings_from_primary = primary_visits

        # Calculate revenue breakdown
        primary_revenue = Decimal("0")
        repeat_revenue = Decimal("0")

        # Map visits to their types
        visit_type_map: dict[int, str] = {}  # external_id -> type
        for item in view.visit_contexts:
            if item.is_primary:
                visit_type_map[int(item.visit.external_id)] = "primary"
            elif item.is_repeat:
                visit_type_map[int(item.visit.external_id)] = "repeat"

        # Extract service mapping to split payments correctly
        visit_service_map: dict[int, int] = defaultdict(int)
        for item in view.visit_contexts:
            service_refs = _extract_visit_service_refs(item.visit)
            visit_service_map[int(item.visit.external_id)] = len(service_refs)

        for payment in view.payments:
            if payment.amount is None:
                continue
            v_id = _parse_intish(payment.visit_external_id)
            if v_id is not None and v_id in visit_type_map:
                v_type = visit_type_map[v_id]
                if v_type == "primary":
                    primary_revenue += payment.amount
                else:
                    repeat_revenue += payment.amount

        payment_amounts = [item.amount for item in view.payments if item.amount is not None]
        payments_total = len(payment_amounts)
        revenue_total = sum(payment_amounts, start=Decimal("0"))
        avg_check = revenue_total / payments_total if payments_total else Decimal("0")
        conversion = (arrived_total / visits_total * 100) if visits_total else 0.0
        primary_conversion = (primary_arrived / primary_visits * 100) if primary_visits else 0.0
        repeat_conversion = (repeat_arrived / repeat_total * 100) if repeat_total else 0.0
        primary_avg = primary_revenue / primary_arrived if primary_arrived else Decimal("0")
        repeat_avg = repeat_revenue / repeat_arrived if repeat_arrived else Decimal("0")

        return AnalyticsOverviewResponse(
            visits_total=visits_total,
            arrived_total=arrived_total,
            primary_visits=primary_visits,
            primary_arrived=primary_arrived,
            conversion_primary_arrived_pct=round(primary_conversion, 2),
            arrived_primary=arrived_primary,
            repeat_total=repeat_total,
            repeat_arrived=repeat_arrived,
            conversion_repeat_arrived_pct=round(repeat_conversion, 2),
            primary_revenue=_round_money(primary_revenue),
            repeat_revenue=_round_money(repeat_revenue),
            primary_avg_check=_round_money(primary_avg),
            repeat_avg_check=_round_money(repeat_avg),
            bookings_from_primary=bookings_from_primary,
            conversion_arrived_to_booked_pct=round(conversion, 2),
            avg_check=_round_money(avg_check),
            revenue_total=_round_money(revenue_total),
            payments_total=payments_total,
            revenue_basis=revenue_basis,
            period_start=period.start_local,
            period_end=period.end_local_exclusive - timedelta(microseconds=1),
            timezone=period.timezone_name,
            last_sync_at=self.agent.sqns_last_sync_at,
        )

    async def get_timeseries(
        self,
        *,
        period: AnalyticsPeriod,
        group_by: AnalyticsTimeGroup,
        channel: str | None,
        client_tags: list[str],
        revenue_basis: AnalyticsRevenueBasis = "all",
        payment_methods: list[str] | None = None,
        revenue_categories: list[str] | None = None,
        resource_external_id: int | None = None,
    ) -> AnalyticsTimeseriesResponse:
        dataset = await self._load_dataset(period)
        view = self._build_view(
            dataset,
            period=period,
            channel=channel,
            client_tags=client_tags,
            revenue_basis=revenue_basis,
            payment_methods=payment_methods,
            revenue_categories=revenue_categories,
            resource_external_id=resource_external_id,
        )

        metrics: dict[str, dict[str, Decimal | int]] = defaultdict(
            lambda: {
                "visits_total": 0,
                "arrived_total": 0,
                "primary_visits": 0,
                "primary_arrived": 0,
                "revenue_total": Decimal("0"),
            }
        )

        for item in view.visit_contexts:
            local_dt = _to_local_datetime(item.visit.visit_datetime, period.tz)
            if local_dt is None:
                continue
            bucket_key = self._bucket_key(local_dt, group_by)
            metrics[bucket_key]["visits_total"] = int(metrics[bucket_key]["visits_total"]) + 1
            if item.is_arrived:
                metrics[bucket_key]["arrived_total"] = int(metrics[bucket_key]["arrived_total"]) + 1
            if item.is_primary:
                metrics[bucket_key]["primary_visits"] = int(metrics[bucket_key]["primary_visits"]) + 1
                if item.is_arrived:
                    metrics[bucket_key]["primary_arrived"] = int(metrics[bucket_key]["primary_arrived"]) + 1

        for payment in view.payments:
            local_dt = _to_local_datetime(payment.payment_date, period.tz)
            if local_dt is None:
                continue
            bucket_key = self._bucket_key(local_dt, group_by)
            amount = payment.amount or Decimal("0")
            metrics[bucket_key]["revenue_total"] = Decimal(metrics[bucket_key]["revenue_total"]) + amount

        points: list[AnalyticsTimeseriesPoint] = []
        for bucket in self._iterate_buckets(period, group_by):
            bucket_key = bucket.isoformat()
            bucket_metrics = metrics.get(
                bucket_key,
                {
                    "visits_total": 0,
                    "arrived_total": 0,
                    "primary_visits": 0,
                    "primary_arrived": 0,
                    "revenue_total": Decimal("0"),
                },
            )
            points.append(
                AnalyticsTimeseriesPoint(
                    bucket=bucket_key,
                    label=self._bucket_label(bucket, group_by),
                    visits_total=int(bucket_metrics["visits_total"]),
                    arrived_total=int(bucket_metrics["arrived_total"]),
                    primary_visits=int(bucket_metrics["primary_visits"]),
                    primary_arrived=int(bucket_metrics["primary_arrived"]),
                    revenue_total=_round_money(Decimal(bucket_metrics["revenue_total"])),
                )
            )

        return AnalyticsTimeseriesResponse(
            group_by=group_by,
            timezone=period.timezone_name,
            period_start=period.start_local,
            period_end=period.end_local_exclusive - timedelta(microseconds=1),
            revenue_basis=revenue_basis,
            points=points,
        )

    async def get_breakdown(
        self,
        *,
        period: AnalyticsPeriod,
        dimension: AnalyticsBreakdownDimension,
        channel: str | None,
        client_tags: list[str],
        limit: int,
        resource_external_id: int | None = None,
    ) -> AnalyticsBreakdownResponse:
        dataset = await self._load_dataset(period)
        view = self._build_view(
            dataset,
            period=period,
            channel=channel,
            client_tags=client_tags,
            resource_external_id=resource_external_id,
        )

        counters: dict[str, int] = defaultdict(int)
        labels: dict[str, str] = {}
        total = 0

        if dimension == "channel":
            for item in view.visit_contexts:
                counters[item.channel] += 1
                labels[item.channel] = _channel_label(item.channel)
                total += 1
        elif dimension == "tag":
            for item in view.visit_contexts:
                if not item.client_tags:
                    continue
                for tag in item.client_tags:
                    counters[tag] += 1
                    labels[tag] = tag
                    total += 1
        else:  # client_type
            for item in view.visit_contexts:
                if item.is_primary:
                    key = "primary"
                    label = "Первичные"
                elif item.is_repeat:
                    key = "repeat"
                    label = "Повторные"
                else:
                    key = "unknown"
                    label = "Не определено"
                counters[key] += 1
                labels[key] = label
                total += 1

        sorted_items = sorted(counters.items(), key=lambda kv: (-kv[1], labels.get(kv[0], kv[0])))
        response_items = [
            AnalyticsBreakdownItem(
                key=key,
                label=labels.get(key, key),
                count=value,
                share=(value / total) if total else 0,
            )
            for key, value in sorted_items[:limit]
        ]

        return AnalyticsBreakdownResponse(
            dimension=dimension,
            total=total,
            items=response_items,
            period_start=period.start_local,
            period_end=period.end_local_exclusive - timedelta(microseconds=1),
            timezone=period.timezone_name,
        )

    async def get_filters_meta(
        self,
        *,
        timezone_name: str | None,
    ) -> AnalyticsFiltersMetaResponse:
        resolved_timezone, tz = _resolve_zoneinfo(timezone_name, self.agent.timezone)

        min_max_stmt = (
            select(func.min(SqnsVisit.visit_datetime), func.max(SqnsVisit.visit_datetime))
            .where(
                SqnsVisit.agent_id == self.agent.id,
                SqnsVisit.visit_datetime.is_not(None),
            )
        )
        min_dt, max_dt = (await self.db.execute(min_max_stmt)).one()
        min_date = _to_local_datetime(min_dt, tz).date() if min_dt else None
        max_date = _to_local_datetime(max_dt, tz).date() if max_dt else None

        channels_stmt = (
            select(SqnsVisit)
            .where(SqnsVisit.agent_id == self.agent.id)
            .order_by(SqnsVisit.visit_datetime.desc().nullslast())
            .limit(_MAX_CHANNEL_SCAN_ROWS)
        )
        channel_rows = (await self.db.execute(channels_stmt)).scalars().all()
        extracted_channels = {_extract_visit_channel(item) for item in channel_rows}

        channel_links_stmt = (
            select(Channel.type)
            .join(AgentChannel, AgentChannel.channel_id == Channel.id)
            .where(
                AgentChannel.agent_id == self.agent.id,
                Channel.is_deleted.is_(False),
            )
        )
        linked_channels = [row[0] for row in (await self.db.execute(channel_links_stmt)).all()]
        extracted_channels.update(_normalize_channel(item) for item in linked_channels)
        extracted_channels.discard("")

        channels = sorted(extracted_channels)

        tags_stmt = select(SqnsClientRecord.tags).where(SqnsClientRecord.agent_id == self.agent.id)
        tag_rows = (await self.db.execute(tags_stmt)).all()
        tag_values: set[str] = set()
        for row in tag_rows:
            raw_tags = row[0] if isinstance(row[0], list) else []
            for item in raw_tags:
                if isinstance(item, str):
                    normalized = _normalize_text(item)
                    if normalized:
                        tag_values.add(normalized)
                    continue
                if isinstance(item, dict):
                    candidate = item.get("name") or item.get("tag") or item.get("value")
                    normalized = _normalize_text(candidate)
                    if normalized:
                        tag_values.add(normalized)

        sorted_tags = sorted(tag_values)[:_MAX_TAG_OPTIONS]

        return AnalyticsFiltersMetaResponse(
            timezone=resolved_timezone,
            default_period_days=_DEFAULT_PERIOD_DAYS,
            min_date=min_date,
            max_date=max_date,
            last_sync_at=self.agent.sqns_last_sync_at,
            available_channels=[
                AnalyticsFilterOption(value=item, label=_channel_label(item))
                for item in channels
            ],
            available_tags=[AnalyticsFilterOption(value=item, label=item) for item in sorted_tags],
            phase2_backlog=list(_PHASE2_BACKLOG),
        )

    async def get_services_table(
        self,
        *,
        period: AnalyticsPeriod,
        channel: str | None,
        client_tags: list[str],
        resource_external_id: int | None,
        sort_by: AnalyticsServicesTableSortBy,
        sort_order: AnalyticsSortOrder,
        limit: int,
        offset: int,
        revenue_basis: AnalyticsRevenueBasis = "all",
        payment_methods: list[str] | None = None,
        revenue_categories: list[str] | None = None,
    ) -> AnalyticsServicesTableResponse:
        dataset = await self._load_dataset(period)
        view = self._build_view(
            dataset,
            period=period,
            channel=channel,
            client_tags=client_tags,
            revenue_basis=revenue_basis,
            payment_methods=payment_methods,
            revenue_categories=revenue_categories,
            resource_external_id=resource_external_id,
        )

        filtered_contexts = view.visit_contexts

        metrics_by_service: dict[str, ServiceMetricsAccumulator] = {}
        visit_service_map: dict[str, list[str]] = {}
        visit_svc_pay_sums: dict[str, dict[str, Decimal]] = {}
        visit_total_costs: dict[str, Decimal] = {}
        used_external_ids: set[int] = set()

        for context in filtered_contexts:
            service_refs = _extract_visit_service_refs(context.visit)
            visit_external_key = str(context.visit.external_id)
            visit_service_keys: list[str] = []
            raw = context.visit.raw_data if isinstance(context.visit.raw_data, dict) else None
            svc_pay_sums = _visit_item_pay_sums(raw, "services")
            visit_svc_pay_sums[visit_external_key] = svc_pay_sums
            visit_total_costs[visit_external_key] = _visit_total_cost(raw)
            for ref in service_refs:
                row = metrics_by_service.get(ref.service_key)
                if row is None:
                    fallback_name = ref.service_name or (
                        f"Услуга #{ref.service_external_id}" if ref.service_external_id is not None else "Не определено"
                    )
                    row = ServiceMetricsAccumulator(
                        service_key=ref.service_key,
                        service_external_id=ref.service_external_id,
                        service_name=fallback_name,
                    )
                    metrics_by_service[ref.service_key] = row
                row.bookings_total += 1
                if context.is_arrived:
                    row.arrived_total += 1
                if context.is_primary:
                    row.primary_total += 1
                    if context.is_arrived:
                        row.primary_arrived_total += 1
                if context.is_repeat:
                    row.repeat_total += 1
                    if context.is_arrived:
                        row.repeat_arrived_total += 1

                if ref.service_external_id is not None:
                    used_external_ids.add(ref.service_external_id)
                visit_service_keys.append(ref.service_key)

            if visit_service_keys:
                visit_service_map[visit_external_key] = visit_service_keys

        if used_external_ids:
            services_stmt = (
                select(SqnsService)
                .where(
                    SqnsService.agent_id == self.agent.id,
                    SqnsService.external_id.in_(used_external_ids),
                )
            )
            services_rows = (await self.db.execute(services_stmt)).scalars().all()
            service_meta_by_external_id = {int(item.external_id): item for item in services_rows}
            for row in metrics_by_service.values():
                if row.service_external_id is None:
                    continue
                meta = service_meta_by_external_id.get(row.service_external_id)
                if meta is None:
                    continue
                row.service_name = meta.name or row.service_name
                row.service_category = meta.category

        for payment in view.payments:
            payment_visit_key = _normalize_text(payment.visit_external_id)
            if not payment_visit_key:
                continue
            linked_service_keys = visit_service_map.get(payment_visit_key)
            if not linked_service_keys:
                continue

            payment_amount = payment.amount or Decimal("0")
            total_cost = visit_total_costs.get(payment_visit_key, Decimal("0"))
            svc_pay_sums = visit_svc_pay_sums.get(payment_visit_key, {})
            total_svc_pay_sum = sum(svc_pay_sums.get(k, Decimal("0")) for k in linked_service_keys)

            for key in linked_service_keys:
                row = metrics_by_service.get(key)
                if row is None:
                    continue
                svc_pay_sum = svc_pay_sums.get(key, Decimal("0"))
                if total_cost > 0 and total_svc_pay_sum > 0:
                    # Proportional: service's share of totalCost applied to payment amount
                    attributed = payment_amount * svc_pay_sum / total_cost
                elif total_svc_pay_sum == 0 and total_cost == Decimal("0"):
                    # Visit billed nothing (e.g. free consultation) — split equally as fallback
                    attributed = payment_amount / Decimal(len(linked_service_keys))
                else:
                    # Service paySum = 0 but visit has other paid items — free service, no revenue
                    attributed = Decimal("0")
                row.revenue_total += attributed
                row.payments_total += 1

        rows = list(metrics_by_service.values())
        for row in rows:
            if row.payments_total > 0:
                avg_check = row.revenue_total / Decimal(row.payments_total)
            else:
                avg_check = Decimal("0")
            row.avg_check = _round_money(avg_check)

        reverse = sort_order == "desc"
        rows.sort(
            key=lambda item: self._service_table_sort_value(item, sort_by),
            reverse=reverse,
        )

        total = len(rows)
        paginated_rows = rows[offset : offset + limit]
        total_bookings = sum(item.bookings_total for item in rows)

        items: list[AnalyticsServiceTableItem] = []
        for row in paginated_rows:
            share_bookings = (row.bookings_total / total_bookings) if total_bookings else 0
            items.append(
                AnalyticsServiceTableItem(
                    service_key=row.service_key,
                    service_external_id=row.service_external_id,
                    service_name=row.service_name,
                    service_category=row.service_category,
                    bookings_total=row.bookings_total,
                    arrived_total=row.arrived_total,
                    primary_total=row.primary_total,
                    primary_arrived_total=row.primary_arrived_total,
                    repeat_total=row.repeat_total,
                    repeat_arrived_total=row.repeat_arrived_total,
                    revenue_total=_round_money(row.revenue_total),
                    payments_total=row.payments_total,
                    avg_check=row.avg_check,
                    share_bookings=share_bookings,
                )
            )

        totals_revenue = sum((item.revenue_total for item in rows), start=Decimal("0"))
        totals_payments = sum(item.payments_total for item in rows)
        totals_avg_check = (
            _round_money(totals_revenue / Decimal(totals_payments))
            if totals_payments
            else 0.0
        )

        totals = AnalyticsServicesTableTotals(
            services_total=total,
            bookings_total=sum(item.bookings_total for item in rows),
            arrived_total=sum(item.arrived_total for item in rows),
            primary_total=sum(item.primary_total for item in rows),
            primary_arrived_total=sum(item.primary_arrived_total for item in rows),
            repeat_total=sum(item.repeat_total for item in rows),
            repeat_arrived_total=sum(item.repeat_arrived_total for item in rows),
            revenue_total=_round_money(totals_revenue),
            payments_total=totals_payments,
            avg_check=totals_avg_check,
        )

        return AnalyticsServicesTableResponse(
            timezone=period.timezone_name,
            period_start=period.start_local,
            period_end=period.end_local_exclusive - timedelta(microseconds=1),
            revenue_basis=revenue_basis,
            last_sync_at=self.agent.sqns_last_sync_at,
            resource_external_id=resource_external_id,
            total=total,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            totals=totals,
            items=items,
        )

    async def get_commodities_table(
        self,
        *,
        period: AnalyticsPeriod,
        channel: str | None,
        client_tags: list[str],
        resource_external_id: int | None,
        sort_by: AnalyticsCommoditiesTableSortBy,
        sort_order: AnalyticsSortOrder,
        limit: int,
        offset: int,
        revenue_basis: AnalyticsRevenueBasis = "all",
        payment_methods: list[str] | None = None,
        revenue_categories: list[str] | None = None,
    ) -> AnalyticsCommoditiesTableResponse:
        dataset = await self._load_dataset(period)
        view = self._build_view(
            dataset,
            period=period,
            channel=channel,
            client_tags=client_tags,
            revenue_basis=revenue_basis,
            payment_methods=payment_methods,
            revenue_categories=revenue_categories,
            resource_external_id=resource_external_id,
        )

        filtered_contexts = view.visit_contexts

        key_meta: dict[str, tuple[int | None, str | None]] = {}
        visit_commodity_keys: dict[int, list[str]] = {}

        metrics_by_commodity: dict[str, CommodityMetricsAccumulator] = {}
        visit_com_pay_sums: dict[str, dict[str, Decimal]] = {}
        visit_total_costs_com: dict[str, Decimal] = {}
        used_external_ids: set[int] = set()

        for context in filtered_contexts:
            raw = context.visit.raw_data if isinstance(context.visit.raw_data, dict) else None
            visit_key = str(context.visit.external_id)
            visit_com_pay_sums[visit_key] = _visit_item_pay_sums(raw, "commodities")
            visit_total_costs_com[visit_key] = _visit_total_cost(raw)

            entries = _visit_commodity_unique_entries(raw)
            keys = [e[0] for e in entries]
            visit_commodity_keys[context.visit.external_id] = keys
            for ck, ext_id, title_hint in entries:
                if ck not in key_meta:
                    key_meta[ck] = (ext_id, title_hint)

            if not keys:
                continue
            for ck in keys:
                ext_id, title_hint = key_meta.get(ck, (None, None))
                row = metrics_by_commodity.get(ck)
                if row is None:
                    fallback_name = title_hint or (
                        f"Товар #{ext_id}" if ext_id is not None else "Не определено"
                    )
                    row = CommodityMetricsAccumulator(
                        commodity_key=ck,
                        commodity_external_id=ext_id,
                        commodity_name=str(fallback_name).strip() if fallback_name else "Не определено",
                    )
                    metrics_by_commodity[ck] = row
                row.bookings_total += 1
                if context.is_arrived:
                    row.arrived_total += 1
                if context.is_primary:
                    row.primary_total += 1
                    if context.is_arrived:
                        row.primary_arrived_total += 1
                if context.is_repeat:
                    row.repeat_total += 1
                    if context.is_arrived:
                        row.repeat_arrived_total += 1
                if ext_id is not None:
                    used_external_ids.add(ext_id)

        if used_external_ids:
            commodities_stmt = select(SqnsCommodity).where(
                SqnsCommodity.agent_id == self.agent.id,
                SqnsCommodity.external_id.in_(used_external_ids),
            )
            commodities_rows = (await self.db.execute(commodities_stmt)).scalars().all()
            commodity_meta_by_ext = {int(item.external_id): item for item in commodities_rows}
            for row in metrics_by_commodity.values():
                if row.commodity_external_id is None:
                    continue
                meta = commodity_meta_by_ext.get(row.commodity_external_id)
                if meta is None:
                    continue
                row.commodity_name = meta.title or row.commodity_name
                row.commodity_category = meta.category

        visit_keys_str_map: dict[str, list[str]] = {
            str(vid): keys for vid, keys in visit_commodity_keys.items()
        }
        for payment in view.payments:
            payment_visit_key = _normalize_text(payment.visit_external_id)
            if not payment_visit_key:
                continue
            linked_keys = visit_keys_str_map.get(payment_visit_key)
            if not linked_keys:
                continue
            payment_amount = payment.amount or Decimal("0")
            total_cost = visit_total_costs_com.get(payment_visit_key, Decimal("0"))
            com_pay_sums = visit_com_pay_sums.get(payment_visit_key, {})
            for ck in linked_keys:
                row = metrics_by_commodity.get(ck)
                if row is None:
                    continue
                com_pay_sum = com_pay_sums.get(ck, Decimal("0"))
                if total_cost > 0 and com_pay_sum > 0:
                    attributed = payment_amount * com_pay_sum / total_cost
                else:
                    # Commodity has no price in this visit (medical supply) — no revenue
                    attributed = Decimal("0")
                row.revenue_total += attributed
                row.payments_total += 1

        acc_rows = list(metrics_by_commodity.values())
        for row in acc_rows:
            if row.payments_total > 0:
                avg_check = row.revenue_total / Decimal(row.payments_total)
            else:
                avg_check = Decimal("0")
            row.avg_check = _round_money(avg_check)

        reverse = sort_order == "desc"
        acc_rows.sort(
            key=lambda item: self._commodity_table_sort_value(item, sort_by),
            reverse=reverse,
        )

        total = len(acc_rows)
        paginated_rows = acc_rows[offset : offset + limit]
        total_bookings = sum(r.bookings_total for r in acc_rows)

        items: list[AnalyticsCommodityTableItem] = []
        for row in paginated_rows:
            share = (row.bookings_total / total_bookings) if total_bookings else 0.0
            items.append(
                AnalyticsCommodityTableItem(
                    commodity_key=row.commodity_key,
                    commodity_external_id=row.commodity_external_id,
                    commodity_name=row.commodity_name,
                    commodity_category=row.commodity_category,
                    bookings_total=row.bookings_total,
                    arrived_total=row.arrived_total,
                    primary_total=row.primary_total,
                    primary_arrived_total=row.primary_arrived_total,
                    repeat_total=row.repeat_total,
                    repeat_arrived_total=row.repeat_arrived_total,
                    revenue_total=float(_round_money(row.revenue_total)),
                    payments_total=row.payments_total,
                    avg_check=row.avg_check,
                    share_bookings=share,
                )
            )

        totals_revenue = sum((r.revenue_total for r in acc_rows), start=Decimal("0"))
        totals_payments = sum(r.payments_total for r in acc_rows)
        totals_avg_check = (
            _round_money(totals_revenue / Decimal(totals_payments)) if totals_payments else 0.0
        )

        totals = AnalyticsCommoditiesTableTotals(
            commodities_total=total,
            bookings_total=sum(r.bookings_total for r in acc_rows),
            arrived_total=sum(r.arrived_total for r in acc_rows),
            primary_total=sum(r.primary_total for r in acc_rows),
            primary_arrived_total=sum(r.primary_arrived_total for r in acc_rows),
            repeat_total=sum(r.repeat_total for r in acc_rows),
            repeat_arrived_total=sum(r.repeat_arrived_total for r in acc_rows),
            revenue_total=float(_round_money(totals_revenue)),
            payments_total=totals_payments,
            avg_check=totals_avg_check,
        )

        return AnalyticsCommoditiesTableResponse(
            timezone=period.timezone_name,
            period_start=period.start_local,
            period_end=period.end_local_exclusive - timedelta(microseconds=1),
            revenue_basis=revenue_basis,
            last_sync_at=self.agent.sqns_last_sync_at,
            resource_external_id=resource_external_id,
            total=total,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            totals=totals,
            items=items,
        )

    async def _load_dataset(self, period: AnalyticsPeriod) -> AnalyticsDataset:
        visits_stmt = (
            select(SqnsVisit)
            .where(
                SqnsVisit.agent_id == self.agent.id,
                SqnsVisit.visit_datetime.is_not(None),
                SqnsVisit.visit_datetime >= period.start_utc,
                SqnsVisit.visit_datetime < period.end_utc,
            )
            .order_by(SqnsVisit.visit_datetime.asc())
        )
        visits = (await self.db.execute(visits_stmt)).scalars().all()

        payments_stmt = (
            select(SqnsPayment)
            .where(
                SqnsPayment.agent_id == self.agent.id,
                SqnsPayment.payment_date.is_not(None),
                SqnsPayment.payment_date >= period.start_utc,
                SqnsPayment.payment_date < period.end_utc,
            )
            .order_by(SqnsPayment.payment_date.asc())
        )
        payments = (await self.db.execute(payments_stmt)).scalars().all()

        client_ids: set[int] = set()
        for visit in visits:
            if visit.client_external_id is not None:
                client_ids.add(int(visit.client_external_id))
        for payment in payments:
            parsed_id = self._parse_client_external_id(payment.client_external_id)
            if parsed_id is not None:
                client_ids.add(parsed_id)

        clients_by_external_id: dict[int, SqnsClientRecord] = {}
        if client_ids:
            clients_stmt = (
                select(SqnsClientRecord)
                .where(
                    SqnsClientRecord.agent_id == self.agent.id,
                    SqnsClientRecord.external_id.in_(client_ids),
                )
            )
            clients = (await self.db.execute(clients_stmt)).scalars().all()
            clients_by_external_id = {int(item.external_id): item for item in clients}

        return AnalyticsDataset(
            visits=visits,
            payments=payments,
            clients_by_external_id=clients_by_external_id,
        )

    def _build_view(
        self,
        dataset: AnalyticsDataset,
        *,
        period: AnalyticsPeriod,
        channel: str | None,
        client_tags: list[str],
        revenue_basis: AnalyticsRevenueBasis = "all",
        payment_methods: list[str] | None = None,
        revenue_categories: list[str] | None = None,
        resource_external_id: int | None = None,
    ) -> AnalyticsView:
        normalized_channel = _normalize_channel(channel) if channel else ""
        normalized_tags = {_normalize_text(tag) for tag in client_tags if _normalize_text(tag)}
        allowed_payment_methods: frozenset[str] | None = None
        if payment_methods:
            allowed_payment_methods = frozenset(_normalize_text(m) for m in payment_methods if _normalize_text(m))

        visit_contexts: list[VisitContext] = []
        allowed_visit_external_ids: set[str] = set()
        narrow_payments_by_visits = bool(
            normalized_channel or normalized_tags or resource_external_id is not None
        )

        for visit in dataset.visits:
            if visit.deleted:
                continue
            client_id = int(visit.client_external_id) if visit.client_external_id is not None else None
            client = dataset.clients_by_external_id.get(client_id) if client_id is not None else None
            tags = _extract_client_tags(client)
            visit_channel = _extract_visit_channel(visit)
            is_primary, is_repeat = _classify_visit_type(visit=visit)

            if normalized_channel and visit_channel != normalized_channel:
                continue
            if normalized_tags and not tags.intersection(normalized_tags):
                continue
            if resource_external_id is not None:
                rid = visit.resource_external_id
                if rid is None or int(rid) != resource_external_id:
                    continue

            context = VisitContext(
                visit=visit,
                client=client,
                channel=visit_channel,
                client_tags=tags,
                is_primary=is_primary,
                is_repeat=is_repeat,
                is_arrived=_is_arrived_visit(visit),
            )
            visit_contexts.append(context)
            allowed_visit_external_ids.add(str(visit.external_id))

        filtered_payments: list[SqnsPayment] = []
        for payment in dataset.payments:
            if not narrow_payments_by_visits:
                filtered_payments.append(payment)
                continue

            payment_visit_id = _normalize_text(payment.visit_external_id)
            if payment_visit_id and payment_visit_id in allowed_visit_external_ids:
                filtered_payments.append(payment)
                continue

            if normalized_channel:
                continue

            if resource_external_id is not None:
                continue

            if normalized_tags:
                client_id = self._parse_client_external_id(payment.client_external_id)
                if client_id is None:
                    continue
                client = dataset.clients_by_external_id.get(client_id)
                if not client:
                    continue
                tags = _extract_client_tags(client)
                if tags.intersection(normalized_tags):
                    filtered_payments.append(payment)

        deduped = _dedupe_payments_for_revenue(filtered_payments)
        if revenue_basis == "clinical":
            deduped = [p for p in deduped if _payment_allowed_for_revenue_basis(p, revenue_basis)]
        if allowed_payment_methods:
            deduped = [
                p for p in deduped
                if _normalize_text(p.payment_method) in allowed_payment_methods
            ]
        allow_type_handles = resolve_revenue_category_handles(revenue_categories)
        if allow_type_handles is not None:
            deduped = [
                p for p in deduped
                if (_normalize_text(p.payment_type_handle) or _normalize_text(p.payment_type_id) or "")
                in allow_type_handles
            ]
        return AnalyticsView(visit_contexts=visit_contexts, payments=deduped)

    @staticmethod
    def _service_table_sort_value(
        item: ServiceMetricsAccumulator,
        sort_by: AnalyticsServicesTableSortBy,
    ) -> str | float | int:
        if sort_by == "service_name":
            return item.service_name.lower()
        if sort_by == "bookings_total":
            return item.bookings_total
        if sort_by == "arrived_total":
            return item.arrived_total
        if sort_by == "primary_total":
            return item.primary_total
        if sort_by == "primary_arrived_total":
            return item.primary_arrived_total
        if sort_by == "repeat_total":
            return item.repeat_total
        if sort_by == "revenue_total":
            return float(item.revenue_total)
        if sort_by == "avg_check":
            return item.avg_check
        return item.bookings_total

    @staticmethod
    def _commodity_table_sort_value(
        item: CommodityMetricsAccumulator,
        sort_by: AnalyticsCommoditiesTableSortBy,
    ) -> str | float | int:
        if sort_by == "commodity_name":
            return item.commodity_name.lower()
        if sort_by == "bookings_total":
            return item.bookings_total
        if sort_by == "arrived_total":
            return item.arrived_total
        if sort_by == "primary_total":
            return item.primary_total
        if sort_by == "primary_arrived_total":
            return item.primary_arrived_total
        if sort_by == "repeat_total":
            return item.repeat_total
        if sort_by == "revenue_total":
            return float(item.revenue_total)
        if sort_by == "avg_check":
            return item.avg_check
        return item.bookings_total

    @staticmethod
    def _parse_client_external_id(value: str | None) -> int | None:
        normalized = _normalize_text(value)
        if not normalized:
            return None
        try:
            return int(normalized)
        except ValueError:
            return None

    @staticmethod
    def _bucket_key(local_dt: datetime, group_by: AnalyticsTimeGroup) -> str:
        local_date = local_dt.date()
        if group_by == "day":
            return local_date.isoformat()
        if group_by == "week":
            week_start = local_date - timedelta(days=local_date.weekday())
            return week_start.isoformat()
        month_start = local_date.replace(day=1)
        return month_start.isoformat()

    @staticmethod
    def _bucket_label(bucket_date: date, group_by: AnalyticsTimeGroup) -> str:
        if group_by == "day":
            return bucket_date.strftime("%d.%m")
        if group_by == "week":
            return f"Нед {bucket_date.strftime('%d.%m')}"
        return bucket_date.strftime("%m.%Y")

    @staticmethod
    def _iterate_buckets(period: AnalyticsPeriod, group_by: AnalyticsTimeGroup) -> list[date]:
        start = period.date_from
        end = period.date_to

        if group_by == "day":
            current = start
            buckets: list[date] = []
            while current <= end:
                buckets.append(current)
                current += timedelta(days=1)
            return buckets

        if group_by == "week":
            current = start - timedelta(days=start.weekday())
            buckets = []
            while current <= end:
                buckets.append(current)
                current += timedelta(days=7)
            return buckets

        # month
        current = start.replace(day=1)
        buckets = []
        while current <= end:
            buckets.append(current)
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)
        return buckets
