from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.services.telegram import TelegramWebhookError, send_telegram_message

logger = structlog.get_logger(__name__)


def _normalize_str(value: str | None) -> str:
    return (value or "").strip()


async def send_wappi_balance_alert(
    *,
    channel_id: str,
    channel_type: str,
    profile_id: str,
    tariff_id: int,
    error_text: str,
) -> None:
    settings = get_settings()
    bot_token = _normalize_str(settings.alerts_telegram_bot_token)
    chat_id = _normalize_str(settings.alerts_telegram_chat_id)
    if not bot_token or not chat_id:
        logger.warning(
            "ops_alert_skipped_missing_telegram_config",
            channel_id=channel_id,
            channel_type=channel_type,
        )
        return

    safe_error_text = (error_text or "").strip()
    if len(safe_error_text) > 1200:
        safe_error_text = f"{safe_error_text[:1200]}..."

    message = (
        "Внимание: недостаточно средств для подключения номера.\n"
        f"Канал: {channel_type}\n"
        f"Channel ID: {channel_id}\n"
        f"Profile ID: {profile_id}\n"
        f"Tariff ID: {tariff_id}\n"
        f"Ошибка: {safe_error_text}"
    )

    try:
        await send_telegram_message(
            bot_token=bot_token,
            chat_id=chat_id,
            text=message,
            timeout_seconds=5,
        )
        logger.info(
            "ops_alert_sent_wappi_balance",
            channel_id=channel_id,
            channel_type=channel_type,
            profile_id=profile_id,
        )
    except (TelegramWebhookError, ValueError) as exc:
        logger.warning(
            "ops_alert_failed_wappi_balance",
            channel_id=channel_id,
            channel_type=channel_type,
            profile_id=profile_id,
            error=str(exc),
        )
