"""Jivo Bot API — исходящая отправка (BOT_MESSAGE).

Ответ бота уходит POST-ом на {reply_base_url}/{provider_id}/{token}, где:
  - reply_base_url — «Путь к ответу» из кабинета Jivo (напр. https://bot.jivosite.com/webhooks);
  - provider_id    — «ID провайдера» из кабинета Jivo (site_id);
  - token          — наш провайдер-токен (генерим при подключении).

Таймаут Jivo на приём вебхука — 3 сек + 2 ретрая, поэтому отправку делаем из фоновой
задачи (после debounce), а не в теле ответа на входящий вебхук.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import uuid4

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Пул соединений можно добавить позже (модульный AsyncClient); сейчас — клиент на вызов,
# как в services/telegram.py, чтобы не тянуть управление жизненным циклом.
_DEFAULT_TIMEOUT_SECONDS = 15
_DEFAULT_MAX_ATTEMPTS = 3


class JivoClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def build_outbound_url(reply_base_url: str, provider_id: str, token: str) -> str:
    """Собрать URL ответа Jivo из базового или полного пути Jivo."""
    base = (reply_base_url or "").rstrip("/")
    suffix = f"/{provider_id}/{token}"
    if base.endswith(suffix):
        return base
    return f"{base}/{provider_id}/{token}"


def is_outbound_configured(reply_base_url: str | None, provider_id: str | None) -> bool:
    """Готов ли канал к отправке ответов (клиент уже ввёл данные из кабинета Jivo)."""
    return bool((reply_base_url or "").strip()) and bool((provider_id or "").strip())


async def send_bot_message(
    *,
    reply_base_url: str,
    provider_id: str,
    token: str,
    client_id: str,
    chat_id: str,
    text: str,
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    """Отправить текстовый ответ бота в Jivo. Ретраи с backoff на сетевые/5xx/429."""
    if not is_outbound_configured(reply_base_url, provider_id):
        raise JivoClientError("Jivo outbound is not configured (provider_id/reply_base_url missing)")
    if not token:
        raise JivoClientError("Jivo provider token is required")
    if not text:
        raise JivoClientError("text is required")

    url = build_outbound_url(reply_base_url, provider_id, token)
    payload: dict[str, Any] = {
        "id": str(uuid4()),
        "client_id": str(client_id),
        "chat_id": str(chat_id),
        "message": {
            "type": "TEXT",
            "text": text,
            "timestamp": int(time.time()),
        },
        "event": "BOT_MESSAGE",
    }

    last_error: JivoClientError | None = None
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            last_error = JivoClientError("Jivo BOT_MESSAGE request failed")
            logger.warning("jivo_send_http_error", attempt=attempt, error=str(exc))
        else:
            if response.status_code < 400:
                try:
                    return response.json() or {}
                except ValueError:
                    return {}
            # 4xx кроме 429 — постоянная ошибка, не ретраим.
            if response.status_code < 500 and response.status_code != 429:
                logger.warning(
                    "jivo_send_failed",
                    status_code=response.status_code,
                    body=response.text[:500],
                )
                raise JivoClientError(
                    f"Jivo BOT_MESSAGE failed with status {response.status_code}",
                    status_code=response.status_code,
                )
            last_error = JivoClientError(
                f"Jivo BOT_MESSAGE failed with status {response.status_code}",
                status_code=response.status_code,
            )
            logger.warning("jivo_send_retryable", attempt=attempt, status_code=response.status_code)

        if attempt < max_attempts - 1:
            await asyncio.sleep(0.5 * (2**attempt))

    raise last_error or JivoClientError("Jivo BOT_MESSAGE failed after retries")
