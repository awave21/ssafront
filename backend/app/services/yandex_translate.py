from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class YandexTranslateError(Exception):
    """Raised when Yandex Translate call fails."""


@dataclass(frozen=True)
class YandexTranslateResult:
    text: str
    detected_language_code: str | None = None


def _build_auth_header(api_key: str) -> str:
    key = api_key.strip()
    if not key:
        raise YandexTranslateError("YANDEX_TRANSLATE_API_KEY is empty")
    # Yandex Translate supports Api-Key and Bearer IAM token auth.
    # Keep auto mode to avoid hardcoding credential type.
    if key.startswith(("AQVN", "AQV")):
        return f"Api-Key {key}"
    return f"Bearer {key}"


async def translate_text(
    *,
    text: str,
    target_language_code: str = "en",
    source_language_code: str | None = None,
) -> YandexTranslateResult:
    settings = get_settings()
    if not settings.yandex_translate_api_key:
        raise YandexTranslateError("Yandex Translate API key is not configured")
    if not settings.yandex_translate_folder_id:
        raise YandexTranslateError("Yandex Translate folder id is not configured")

    payload: dict[str, Any] = {
        "targetLanguageCode": target_language_code,
        "texts": [text],
        "folderId": settings.yandex_translate_folder_id,
    }
    if source_language_code:
        payload["sourceLanguageCode"] = source_language_code

    headers = {
        "Authorization": _build_auth_header(settings.yandex_translate_api_key),
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.yandex_translate_timeout_seconds) as client:
            response = await client.post(
                settings.yandex_translate_url,
                json=payload,
                headers=headers,
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500]
        logger.warning(
            "yandex_translate_http_status_error",
            status_code=exc.response.status_code,
            body=body,
        )
        raise YandexTranslateError(f"Yandex translate error: {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        logger.warning("yandex_translate_http_error", error=str(exc))
        raise YandexTranslateError("Yandex translate request failed") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise YandexTranslateError("Yandex translate returned invalid JSON") from exc

    translations = data.get("translations")
    if not isinstance(translations, list) or not translations:
        raise YandexTranslateError("Yandex translate response has no translations")
    first = translations[0]
    translated_text = str(first.get("text") or "").strip()
    if not translated_text:
        raise YandexTranslateError("Yandex translate returned empty translation")
    return YandexTranslateResult(
        text=translated_text,
        detected_language_code=(
            str(first.get("detectedLanguageCode"))
            if first.get("detectedLanguageCode") is not None
            else None
        ),
    )
