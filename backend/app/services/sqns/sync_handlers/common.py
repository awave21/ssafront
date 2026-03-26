from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re
from typing import Any


def coerce_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        normalized = text.replace(" ", "").replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            cleaned = re.sub(r"[^0-9.+-]", "", normalized)
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
    if isinstance(value, dict):
        for key in (
            "value",
            "amount",
            "price",
            "sum",
            "total",
            "from",
            "min",
            "range",
            "minPrice",
            "min_price",
        ):
            if key not in value:
                continue
            candidate = coerce_number(value.get(key))
            if candidate is not None:
                return candidate
        if len(value) == 1:
            return coerce_number(next(iter(value.values())))
    if isinstance(value, (list, tuple)):
        for item in value:
            candidate = coerce_number(item)
            if candidate is not None:
                return candidate
    return None


def parse_decimal(value: Any) -> Decimal | None:
    parsed = coerce_number(value)
    if parsed is None:
        return None
    return Decimal(str(parsed))


def parse_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
    return default


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000.0
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return parse_datetime(int(text))
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def unwrap_payload_list(
    value: Any,
    *,
    extra_nested_keys: tuple[str, ...] = (),
) -> list[Any] | None:
    """SQNS often wraps arrays as { \"data\": [...] } or nests them under alternate keys."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("data", "items", "result") + extra_nested_keys:
            inner = value.get(key)
            if isinstance(inner, list):
                return inner
    return None


def compose_employee_name(employee: dict[str, Any]) -> str | None:
    parts: list[str] = []
    for key in ("lastname", "firstname", "patronymic"):
        raw_value = employee.get(key)
        if raw_value is None:
            continue
        text = str(raw_value).strip()
        if text:
            parts.append(text)
    if parts:
        return " ".join(parts)
    for key in ("name", "fullName", "title", "fio", "displayName"):
        raw_value = employee.get(key)
        if raw_value is None:
            continue
        text = str(raw_value).strip()
        if text:
            return text
    return None


def build_payment_external_id(payload: dict[str, Any]) -> str:
    key_payload = {
        "date": payload.get("date"),
        "paymentMethod": payload.get("paymentMethod"),
        "paymentTypeId": payload.get("paymentTypeId"),
        "paymentTypeHandle": payload.get("paymentTypeHandle"),
        "organizationId": payload.get("organizationId"),
        "clientId": payload.get("clientId"),
        "visitId": payload.get("visitId"),
        "amount": payload.get("amount"),
        "comment": payload.get("comment"),
    }
    serialized = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
