"""
Определение факта визита (пациент пришёл / визит завершён) для SQNS-кэша.

Согласовано с логикой аналитики: attendance > 0 из API, иначе эвристика по тексту status в raw_data.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.db.models.sqns_service import SqnsVisit

# Подстроки в нижнем регистре (см. _normalize_text)
_ARRIVED_STATUS_MARKERS = (
    "arrived",
    "completed",
    "done",
    "visited",
    "finish",
    "пришел",
    "пришёл",
    "явка",
    "заверш",
)
_NOT_ARRIVED_STATUS_MARKERS = (
    "cancel",
    "canceled",
    "cancelled",
    "no_show",
    "noshow",
    "отмен",
)


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


def is_sqns_visit_arrived(visit: SqnsVisit) -> bool:
    """True, если визит считается состоявшимся (пациент пришёл / завершён), не отмена."""
    if visit.deleted:
        return False
    if visit.attendance is not None:
        return int(visit.attendance) > 0

    raw = visit.raw_data if isinstance(visit.raw_data, dict) else None
    status_value = _read_nested(
        raw,
        (("status",), ("visit", "status"), ("appointment", "status")),
    )
    normalized_status = _normalize_text(status_value)
    if not normalized_status:
        return False
    if any(marker in normalized_status for marker in _NOT_ARRIVED_STATUS_MARKERS):
        return False
    return any(marker in normalized_status for marker in _ARRIVED_STATUS_MARKERS)
