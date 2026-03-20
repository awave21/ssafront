from __future__ import annotations

from typing import Any
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import structlog

logger = structlog.get_logger(__name__)


def _safe_identifier(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if not safe or safe[0].isdigit():
        safe = f"tool_{safe}"
    return safe


def _enrich_system_prompt_with_datetime(system_prompt: str, tz_name: str = "UTC") -> str:
    """
    Добавляет переменные даты и времени в системный промпт для корректного поиска свободных слотов.

    Args:
        system_prompt: Исходный системный промпт
        tz_name: IANA часовой пояс агента (например, "Europe/Moscow", "UTC")

    Returns:
        Обогащенный системный промпт с переменными даты и времени в указанном часовом поясе
    """
    if not system_prompt:
        return system_prompt

    try:
        tz = ZoneInfo(tz_name)
    except (KeyError, Exception):
        logger.warning("invalid_timezone_fallback_utc", tz_name=tz_name)
        tz = ZoneInfo("UTC")
        tz_name = "UTC"

    now = datetime.now(tz)

    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    current_datetime = now.strftime("%Y-%m-%d %H:%M:%S")
    current_datetime_iso = now.isoformat()

    current_date_ru = now.strftime("%d.%m.%Y")
    current_time_ru = now.strftime("%H:%M")
    current_datetime_ru = now.strftime("%d.%m.%Y %H:%M")

    # Вычисляем UTC offset для наглядности (например, "UTC+3", "UTC-5")
    utc_offset = now.strftime("%z")
    if utc_offset:
        hours = int(utc_offset[:3])
        minutes = int(utc_offset[0] + utc_offset[3:5])
        offset_str = f"UTC{hours:+d}" if minutes == 0 else f"UTC{utc_offset[:3]}:{utc_offset[3:5]}"
    else:
        offset_str = "UTC"

    datetime_context = f"""
---
Текущая дата и время:
- Дата: {current_date} ({current_date_ru})
- Время: {current_time} ({current_time_ru})
- Дата и время: {current_datetime} ({current_datetime_ru})
- ISO формат: {current_datetime_iso}
- Часовой пояс: {tz_name} ({offset_str})
"""

    return system_prompt + "\n" + datetime_context


def _sanitize_output(text: str) -> str:
    """Оставить только текст ответа, убрать repr-обертки."""
    if not text or not isinstance(text, str):
        return ""
    m = re.match(r"^AgentRunResult\(output=['\"](.+)['\"]\)\s*$", text.strip(), re.DOTALL)
    if m:
        text = m.group(1)
    elif text.strip().startswith("AgentRunResult("):
        inner = re.search(r"output=['\"](.+?)['\"]\)\s*$", text, re.DOTALL)
        if inner:
            text = inner.group(1)
    return text.replace("\\n", "\n").replace("\\t", "\t")


def _normalize_token_value(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_usage_field(usage: Any, keys: tuple[str, ...]) -> int | None:
    for key in keys:
        if hasattr(usage, key):
            value = _normalize_token_value(getattr(usage, key, None))
            if value is not None:
                return value
        if isinstance(usage, dict):
            value = _normalize_token_value(usage.get(key))
            if value is not None:
                return value
    return None


def _extract_usage_details_object(usage: Any) -> Any:
    detail_keys = (
        "input_tokens_details",
        "prompt_tokens_details",
        "input_token_details",
        "prompt_token_details",
        "details",
        "usage_details",
    )
    for key in detail_keys:
        if hasattr(usage, key):
            details_obj = getattr(usage, key, None)
            if details_obj is not None:
                return details_obj
        if isinstance(usage, dict):
            details_obj = usage.get(key)
            if details_obj is not None:
                return details_obj
    return None


def _extract_usage_detail_tokens(usage: Any) -> dict[str, int | None]:
    details_obj = _extract_usage_details_object(usage)

    def _from_usage_or_details(*keys: str) -> int | None:
        usage_value = _extract_usage_field(usage, tuple(keys))
        if usage_value is not None:
            return usage_value
        if details_obj is not None:
            return _extract_usage_field(details_obj, tuple(keys))
        return None

    return {
        "cache_read_tokens": _from_usage_or_details(
            "cache_read_tokens",
            "cache_read_input_tokens",
            "cached_tokens",
        ),
        "cache_write_tokens": _from_usage_or_details("cache_write_tokens"),
        "reasoning_tokens": _from_usage_or_details("reasoning_tokens"),
        "audio_tokens": _from_usage_or_details("audio_tokens"),
        "input_audio_tokens": _from_usage_or_details("input_audio_tokens"),
        "output_audio_tokens": _from_usage_or_details("output_audio_tokens"),
        "cache_audio_read_tokens": _from_usage_or_details("cache_audio_read_tokens"),
        "accepted_prediction_tokens": _from_usage_or_details("accepted_prediction_tokens"),
        "rejected_prediction_tokens": _from_usage_or_details("rejected_prediction_tokens"),
    }


def _extract_usage_values(usage: Any) -> tuple[int | None, int | None, int | None]:
    prompt_tokens = None
    completion_tokens = None
    total_tokens = None

    if usage is None:
        return prompt_tokens, completion_tokens, total_tokens

    prompt_tokens = _extract_usage_field(usage, ("prompt_tokens", "input_tokens", "request_tokens"))
    completion_tokens = _extract_usage_field(usage, ("completion_tokens", "output_tokens", "response_tokens"))
    total_tokens = _extract_usage_field(usage, ("total_tokens",))

    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    return prompt_tokens, completion_tokens, total_tokens


def _extract_input_token_breakdown(usage: Any, prompt_tokens: int | None) -> tuple[int | None, int | None]:
    """
    Извлечь cached/non-cached input токены из usage details.

    Если details отсутствуют, считаем весь input как non-cached.
    """
    if usage is None:
        return None, prompt_tokens

    details_obj = _extract_usage_details_object(usage)
    detail_tokens = _extract_usage_detail_tokens(usage)

    cached_tokens = detail_tokens["cache_read_tokens"]
    if cached_tokens is None and details_obj is not None:
        cached_tokens = _extract_usage_field(
            details_obj,
            ("cached_tokens", "cache_read_input_tokens", "cache_read_tokens"),
        )

    effective_prompt = prompt_tokens
    if effective_prompt is None:
        effective_prompt = _extract_usage_field(usage, ("input_tokens", "prompt_tokens"))
    if effective_prompt is None and details_obj is not None:
        effective_prompt = _extract_usage_field(details_obj, ("input_tokens", "prompt_tokens", "total_tokens"))

    if cached_tokens is not None and effective_prompt is not None:
        cached_tokens = min(cached_tokens, effective_prompt)
        non_cached_tokens = max(effective_prompt - cached_tokens, 0)
        return cached_tokens, non_cached_tokens

    if effective_prompt is not None:
        return cached_tokens, effective_prompt

    return cached_tokens, None
