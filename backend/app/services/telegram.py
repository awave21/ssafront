from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class TelegramWebhookError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


async def set_telegram_webhook(
    *,
    bot_token: str,
    webhook_url: str,
    secret_token: str,
    timeout_seconds: int = 15,
) -> dict[str, Any]:
    if not bot_token:
        raise ValueError("bot_token is required")
    if not webhook_url:
        raise ValueError("webhook_url is required")
    if not secret_token:
        raise ValueError("secret_token is required")

    url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    payload = {"url": webhook_url, "secret_token": secret_token}

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        logger.warning("telegram_set_webhook_http_error", error=str(exc))
        raise TelegramWebhookError("Telegram setWebhook request failed") from exc

    if response.status_code >= 400:
        logger.warning("telegram_set_webhook_failed", status_code=response.status_code)
        raise TelegramWebhookError(f"Telegram setWebhook failed with status {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("telegram_set_webhook_invalid_response", status_code=response.status_code)
        raise TelegramWebhookError("Telegram setWebhook returned invalid JSON") from exc

    if not isinstance(data, dict) or not data.get("ok"):
        logger.warning("telegram_set_webhook_not_ok", status_code=response.status_code, response=data)
        raise TelegramWebhookError("Telegram setWebhook returned ok=false")

    logger.info("telegram_set_webhook_success", status_code=response.status_code)
    return data


async def send_telegram_message(
    *,
    bot_token: str,
    chat_id: int | str,
    text: str,
    parse_mode: str | None = None,
    timeout_seconds: int = 15,
) -> dict[str, Any]:
    """Отправить сообщение в Telegram чат.
    parse_mode: "Markdown" | "MarkdownV2" | "HTML" — форматирование текста."""
    if not bot_token:
        raise ValueError("bot_token is required")
    if not text:
        raise ValueError("text is required")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        logger.warning("telegram_send_message_http_error", error=str(exc))
        raise TelegramWebhookError("Telegram sendMessage request failed") from exc

    if response.status_code >= 400:
        retry_after_seconds: int | None = None
        try:
            data = response.json()
            if isinstance(data, dict):
                params = data.get("parameters")
                if isinstance(params, dict) and params.get("retry_after") is not None:
                    retry_after_seconds = int(params["retry_after"])
        except Exception:
            retry_after_seconds = None
        logger.warning(
            "telegram_send_message_failed",
            status_code=response.status_code,
            response_body=response.text[:500],
            retry_after_seconds=retry_after_seconds,
        )
        raise TelegramWebhookError(
            f"Telegram sendMessage failed with status {response.status_code}",
            status_code=response.status_code,
            retry_after_seconds=retry_after_seconds,
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise TelegramWebhookError("Telegram sendMessage returned invalid JSON") from exc

    if not isinstance(data, dict) or not data.get("ok"):
        logger.warning("telegram_send_message_not_ok", response=data)
        raise TelegramWebhookError("Telegram sendMessage returned ok=false")

    return data


async def send_telegram_chat_action(
    *,
    bot_token: str,
    chat_id: int,
    action: str = "typing",
    timeout_seconds: int = 5,
) -> dict[str, Any]:
    """Показать индикатор действия в чате (например, «печатает…»)."""
    if not bot_token:
        raise ValueError("bot_token is required")

    url = f"https://api.telegram.org/bot{bot_token}/sendChatAction"
    payload = {"chat_id": chat_id, "action": action}

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError:
        pass
    else:
        if response.status_code < 400:
            try:
                return response.json() or {}
            except ValueError:
                pass
    return {}
