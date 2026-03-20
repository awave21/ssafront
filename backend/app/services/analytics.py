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
from app.db.models.sqns_service import SqnsClientRecord, SqnsPayment, SqnsService, SqnsVisit
from app.schemas.analytics import (
    AnalyticsBreakdownDimension,
    AnalyticsBreakdownItem,
    AnalyticsBreakdownResponse,
    AnalyticsFilterOption,
    AnalyticsFiltersMetaResponse,
    AnalyticsOverviewResponse,
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

_PRIMARY_CLIENT_MARKERS = ("primary", "new", "first", "перв", "нов")
_REPEAT_CLIENT_MARKERS = ("repeat", "secondary", "повтор", "втор")
_PRIMARY_VISIT_MARKERS = ("primary", "new", "first", "перв", "вперв")
_REPEAT_VISIT_MARKERS = ("repeat", "secondary", "повтор", "втор")
_ARRIVED_STATUS_MARKERS = ("arrived", "completed", "done", "visited", "finish", "пришел", "явка")
_NOT_ARRIVED_STATUS_MARKERS = ("cancel", "canceled", "cancelled", "no_show", "noshow", "отмен")
_VISIT_TIME_MATCH_TOLERANCE_SECONDS = 60

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
    is_existing: bool
    is_arrived: bool


@dataclass
class AnalyticsDataset:
    visits: list[SqnsVisit]
    payments: list[SqnsPayment]
    clients_by_external_id: dict[int, SqnsClientRecord]
    first_visit_at_by_client: dict[int, datetime]


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


def _normalize_client_type(value: str | None) -> str:
    return _normalize_text(value)


def _is_primary_client_profile(client: SqnsClientRecord | None) -> bool:
    if client is None:
        return False
    normalized_type = _normalize_client_type(client.client_type)
    if any(marker in normalized_type for marker in _PRIMARY_CLIENT_MARKERS):
        return True
    if any(marker in normalized_type for marker in _REPEAT_CLIENT_MARKERS):
        return False
    if client.visits_count is not None:
        return int(client.visits_count) <= 1
    return False


def _is_repeat_client_profile(client: SqnsClientRecord | None) -> bool:
    if client is None:
        return False
    normalized_type = _normalize_client_type(client.client_type)
    if any(marker in normalized_type for marker in _REPEAT_CLIENT_MARKERS):
        return True
    if any(marker in normalized_type for marker in _PRIMARY_CLIENT_MARKERS):
        return False
    if client.visits_count is not None:
        return int(client.visits_count) > 1
    return False


def _is_existing_client_profile(client: SqnsClientRecord | None) -> bool:
    if client is None:
        return False
    if _is_repeat_client_profile(client):
        return True
    if _is_primary_client_profile(client):
        return False
    if client.visits_count is not None:
        return int(client.visits_count) > 0
    return True


def _coerce_boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = _normalize_text(value)
        if normalized in {"1", "true", "yes", "y", "да"}:
            return True
        if normalized in {"0", "false", "no", "n", "нет"}:
            return False
    return None


def _extract_visit_primary_hint(visit: SqnsVisit) -> bool | None:
    raw = visit.raw_data if isinstance(visit.raw_data, dict) else None
    if raw is None:
        return None

    direct_value = _read_nested(
        raw,
        (
            ("isPrimary",),
            ("primary",),
            ("is_primary",),
            ("firstVisit",),
            ("first_visit",),
            ("isFirstVisit",),
            ("newClient",),
            ("new_client",),
            ("visit", "isPrimary"),
            ("appointment", "isPrimary"),
        ),
    )
    direct_hint = _coerce_boolish(direct_value)
    if direct_hint is not None:
        return direct_hint

    type_value = _read_nested(
        raw,
        (
            ("visitType",),
            ("visit_type",),
            ("type",),
            ("kind",),
            ("clientType",),
            ("client_type",),
            ("visit", "type"),
            ("visit", "visitType"),
            ("appointment", "type"),
            ("appointment", "visitType"),
            ("client", "type"),
        ),
    )
    normalized_type = _normalize_text(type_value)
    if not normalized_type:
        return None
    if any(marker in normalized_type for marker in _PRIMARY_VISIT_MARKERS):
        return True
    if any(marker in normalized_type for marker in _REPEAT_VISIT_MARKERS):
        return False
    return None


def _extract_visit_repeat_hint(visit: SqnsVisit) -> bool | None:
    raw = visit.raw_data if isinstance(visit.raw_data, dict) else None
    if raw is None:
        return None

    direct_value = _read_nested(
        raw,
        (
            ("isRepeat",),
            ("repeat",),
            ("is_repeat",),
            ("secondary",),
            ("isSecondary",),
            ("visit", "isRepeat"),
            ("appointment", "isRepeat"),
        ),
    )
    direct_hint = _coerce_boolish(direct_value)
    if direct_hint is not None:
        return direct_hint

    type_value = _read_nested(
        raw,
        (
            ("visitType",),
            ("visit_type",),
            ("type",),
            ("kind",),
            ("clientType",),
            ("client_type",),
            ("visit", "type"),
            ("visit", "visitType"),
            ("appointment", "type"),
            ("appointment", "visitType"),
            ("client", "type"),
        ),
    )
    normalized_type = _normalize_text(type_value)
    if not normalized_type:
        return None
    if any(marker in normalized_type for marker in _REPEAT_VISIT_MARKERS):
        return True
    if any(marker in normalized_type for marker in _PRIMARY_VISIT_MARKERS):
        return False
    return None


def _to_utc_datetime(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("UTC"))


def _is_same_visit_moment(current: datetime | None, first: datetime | None) -> bool:
    current_utc = _to_utc_datetime(current)
    first_utc = _to_utc_datetime(first)
    if current_utc is None or first_utc is None:
        return False
    diff_seconds = abs((current_utc - first_utc).total_seconds())
    return diff_seconds <= _VISIT_TIME_MATCH_TOLERANCE_SECONDS


def _is_after_first_visit(current: datetime | None, first: datetime | None) -> bool:
    current_utc = _to_utc_datetime(current)
    first_utc = _to_utc_datetime(first)
    if current_utc is None or first_utc is None:
        return False
    return (current_utc - first_utc).total_seconds() > _VISIT_TIME_MATCH_TOLERANCE_SECONDS


def _classify_visit_type(
    *,
    visit: SqnsVisit,
    client: SqnsClientRecord | None,
    first_visit_at: datetime | None,
) -> tuple[bool, bool]:
    primary_hint = _extract_visit_primary_hint(visit)
    repeat_hint = _extract_visit_repeat_hint(visit)

    if primary_hint is True:
        return True, False
    if repeat_hint is True:
        return False, True

    if _is_same_visit_moment(visit.visit_datetime, first_visit_at):
        return True, False
    if _is_after_first_visit(visit.visit_datetime, first_visit_at):
        return False, True

    if primary_hint is False and repeat_hint is False:
        return False, False

    if _is_primary_client_profile(client):
        return True, False
    if _is_repeat_client_profile(client):
        return False, True
    return False, False


def _is_existing_for_period(
    *,
    period: AnalyticsPeriod,
    client: SqnsClientRecord | None,
    first_visit_at: datetime | None,
    is_primary: bool,
    is_repeat: bool,
) -> bool:
    first_utc = _to_utc_datetime(first_visit_at)
    if first_utc is not None:
        return first_utc < period.start_utc
    if is_repeat:
        return True
    if is_primary:
        return False
    return _is_existing_client_profile(client)


def _is_arrived_visit(visit: SqnsVisit) -> bool:
    if visit.deleted:
        return False
    if visit.attendance is not None:
        return int(visit.attendance) > 0

    raw = visit.raw_data if isinstance(visit.raw_data, dict) else None
    status_value = _read_nested(raw, (("status",), ("visit", "status"), ("appointment", "status")))
    normalized_status = _normalize_text(status_value)
    if not normalized_status:
        return False
    if any(marker in normalized_status for marker in _NOT_ARRIVED_STATUS_MARKERS):
        return False
    return any(marker in normalized_status for marker in _ARRIVED_STATUS_MARKERS)


def _to_local_datetime(dt: datetime | None, tz: ZoneInfo) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    return dt.astimezone(tz)


def _round_money(value: Decimal) -> float:
    return round(float(value), 2)


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
    ) -> AnalyticsOverviewResponse:
        dataset = await self._load_dataset(period)
        view = self._build_view(dataset, period=period, channel=channel, client_tags=client_tags)

        visits_total = len(view.visit_contexts)
        arrived_total = sum(1 for item in view.visit_contexts if item.is_arrived)
        arrived_primary = sum(1 for item in view.visit_contexts if item.is_arrived and item.is_primary)
        repeat_total = sum(1 for item in view.visit_contexts if item.is_repeat)
        bookings_from_primary = sum(1 for item in view.visit_contexts if item.is_primary)
        bookings_from_existing = sum(1 for item in view.visit_contexts if item.is_existing)

        payment_amounts = [item.amount for item in view.payments if item.amount is not None]
        payments_total = len(payment_amounts)
        revenue_total = sum(payment_amounts, start=Decimal("0"))
        avg_check = revenue_total / payments_total if payments_total else Decimal("0")
        conversion = (arrived_total / visits_total * 100) if visits_total else 0.0

        return AnalyticsOverviewResponse(
            visits_total=visits_total,
            arrived_total=arrived_total,
            arrived_primary=arrived_primary,
            repeat_total=repeat_total,
            bookings_from_primary=bookings_from_primary,
            bookings_from_existing_patients=bookings_from_existing,
            conversion_arrived_to_booked_pct=round(conversion, 2),
            avg_check=_round_money(avg_check),
            revenue_total=_round_money(revenue_total),
            payments_total=payments_total,
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
    ) -> AnalyticsTimeseriesResponse:
        dataset = await self._load_dataset(period)
        view = self._build_view(dataset, period=period, channel=channel, client_tags=client_tags)

        metrics: dict[str, dict[str, Decimal | int]] = defaultdict(
            lambda: {"visits_total": 0, "arrived_total": 0, "revenue_total": Decimal("0")}
        )

        for item in view.visit_contexts:
            local_dt = _to_local_datetime(item.visit.visit_datetime, period.tz)
            if local_dt is None:
                continue
            bucket_key = self._bucket_key(local_dt, group_by)
            metrics[bucket_key]["visits_total"] = int(metrics[bucket_key]["visits_total"]) + 1
            if item.is_arrived:
                metrics[bucket_key]["arrived_total"] = int(metrics[bucket_key]["arrived_total"]) + 1

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
            bucket_metrics = metrics.get(bucket_key, {"visits_total": 0, "arrived_total": 0, "revenue_total": Decimal("0")})
            points.append(
                AnalyticsTimeseriesPoint(
                    bucket=bucket_key,
                    label=self._bucket_label(bucket, group_by),
                    visits_total=int(bucket_metrics["visits_total"]),
                    arrived_total=int(bucket_metrics["arrived_total"]),
                    revenue_total=_round_money(Decimal(bucket_metrics["revenue_total"])),
                )
            )

        return AnalyticsTimeseriesResponse(
            group_by=group_by,
            timezone=period.timezone_name,
            period_start=period.start_local,
            period_end=period.end_local_exclusive - timedelta(microseconds=1),
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
    ) -> AnalyticsBreakdownResponse:
        dataset = await self._load_dataset(period)
        view = self._build_view(dataset, period=period, channel=channel, client_tags=client_tags)

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
    ) -> AnalyticsServicesTableResponse:
        dataset = await self._load_dataset(period)
        view = self._build_view(dataset, period=period, channel=channel, client_tags=client_tags)

        filtered_contexts: list[VisitContext] = []
        for item in view.visit_contexts:
            if resource_external_id is not None and item.visit.resource_external_id != resource_external_id:
                continue
            filtered_contexts.append(item)

        metrics_by_service: dict[str, ServiceMetricsAccumulator] = {}
        visit_service_map: dict[str, list[str]] = {}
        used_external_ids: set[int] = set()

        for context in filtered_contexts:
            service_refs = _extract_visit_service_refs(context.visit)
            visit_external_key = str(context.visit.external_id)
            visit_service_keys: list[str] = []
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
            if linked_service_keys:
                split_amount = payment_amount / Decimal(len(linked_service_keys))
            else:
                split_amount = Decimal("0")

            for key in linked_service_keys:
                row = metrics_by_service.get(key)
                if row is None:
                    continue
                row.revenue_total += split_amount
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
        first_visit_at_by_client: dict[int, datetime] = {}
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

            first_visit_stmt = (
                select(
                    SqnsVisit.client_external_id,
                    func.min(SqnsVisit.visit_datetime),
                )
                .where(
                    SqnsVisit.agent_id == self.agent.id,
                    SqnsVisit.client_external_id.in_(client_ids),
                    SqnsVisit.deleted.is_(False),
                    SqnsVisit.visit_datetime.is_not(None),
                )
                .group_by(SqnsVisit.client_external_id)
            )
            first_visit_rows = (await self.db.execute(first_visit_stmt)).all()
            first_visit_at_by_client = {
                int(row[0]): row[1]
                for row in first_visit_rows
                if row[0] is not None and row[1] is not None
            }

        return AnalyticsDataset(
            visits=visits,
            payments=payments,
            clients_by_external_id=clients_by_external_id,
            first_visit_at_by_client=first_visit_at_by_client,
        )

    def _build_view(
        self,
        dataset: AnalyticsDataset,
        *,
        period: AnalyticsPeriod,
        channel: str | None,
        client_tags: list[str],
    ) -> AnalyticsView:
        normalized_channel = _normalize_channel(channel) if channel else ""
        normalized_tags = {_normalize_text(tag) for tag in client_tags if _normalize_text(tag)}

        visit_contexts: list[VisitContext] = []
        allowed_visit_external_ids: set[str] = set()

        for visit in dataset.visits:
            if visit.deleted:
                continue
            client_id = int(visit.client_external_id) if visit.client_external_id is not None else None
            client = dataset.clients_by_external_id.get(client_id) if client_id is not None else None
            first_visit_at = dataset.first_visit_at_by_client.get(client_id) if client_id is not None else None
            tags = _extract_client_tags(client)
            visit_channel = _extract_visit_channel(visit)
            is_primary, is_repeat = _classify_visit_type(
                visit=visit,
                client=client,
                first_visit_at=first_visit_at,
            )
            is_existing = _is_existing_for_period(
                period=period,
                client=client,
                first_visit_at=first_visit_at,
                is_primary=is_primary,
                is_repeat=is_repeat,
            )

            if normalized_channel and visit_channel != normalized_channel:
                continue
            if normalized_tags and not tags.intersection(normalized_tags):
                continue

            context = VisitContext(
                visit=visit,
                client=client,
                channel=visit_channel,
                client_tags=tags,
                is_primary=is_primary,
                is_repeat=is_repeat,
                is_existing=is_existing,
                is_arrived=_is_arrived_visit(visit),
            )
            visit_contexts.append(context)
            allowed_visit_external_ids.add(str(visit.external_id))

        filtered_payments: list[SqnsPayment] = []
        for payment in dataset.payments:
            if not normalized_channel and not normalized_tags:
                filtered_payments.append(payment)
                continue

            payment_visit_id = _normalize_text(payment.visit_external_id)
            if payment_visit_id and payment_visit_id in allowed_visit_external_ids:
                filtered_payments.append(payment)
                continue

            if normalized_channel:
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

        return AnalyticsView(visit_contexts=visit_contexts, payments=filtered_payments)

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
