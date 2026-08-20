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


async def send_manager_pause_alert(
    *,
    bot_token: str | None,
    chat_id: str | None,
    agent_name: str,
    session_id: str,
    reason: str | None = None,
    last_client_message: str | None = None,
    last_agent_message: str | None = None,
) -> bool:
    """Отправить уведомление менеджеру о постановке диалога на паузу.

    Возвращает True при успешной отправке, False при пропуске (нет токена/чата)
    или ошибке отправки. Ошибки не пробрасываются, только логируются — это
    вспомогательный побочный эффект и не должен ломать основной цикл.
    """
    bot_token = _normalize_str(bot_token)
    chat_id = _normalize_str(chat_id)
    if not bot_token or not chat_id:
        logger.debug(
            "manager_pause_alert_skipped_missing_config",
            agent_name=agent_name,
            session_id=session_id,
            has_token=bool(bot_token),
            has_chat_id=bool(chat_id),
        )
        return False

    parts: list[str] = [f"Диалог поставлен на паузу — требуется внимание"]
    parts.append(f"Агент: {agent_name}")
    parts.append(f"Сессия: {session_id}")
    if reason:
        parts.append(f"Причина: {reason}")
    if last_client_message:
        snippet = last_client_message.strip()
        if len(snippet) > 400:
            snippet = snippet[:400] + "..."
        parts.append(f"\nСообщение клиента:\n{snippet}")
    if last_agent_message:
        snippet = last_agent_message.strip()
        if len(snippet) > 400:
            snippet = snippet[:400] + "..."
        parts.append(f"\nОтвет агента:\n{snippet}")

    text = "\n".join(parts)

    try:
        await send_telegram_message(
            bot_token=bot_token,
            chat_id=chat_id,
            text=text,
            timeout_seconds=5,
        )
        logger.info(
            "manager_pause_alert_sent",
            agent_name=agent_name,
            session_id=session_id,
        )
        return True
    except (TelegramWebhookError, ValueError) as exc:
        logger.warning(
            "manager_pause_alert_failed",
            agent_name=agent_name,
            session_id=session_id,
            error=str(exc),
        )
        return False


async def send_admin_notification(
    *,
    bot_token: str | None,
    chat_id: str | None,
    agent_name: str,
    session_id: str,
    message: str | None = None,
    last_client_message: str | None = None,
) -> bool:
    """Отправить администратору произвольное уведомление в Telegram.

    В отличие от `send_manager_pause_alert`, не привязано к паузе диалога: текст
    задаёт автор правила в действии `notify_admin`, поэтому заголовок нейтральный.
    Если текст не задан — уходит минимальная сводка (агент + сессия), чтобы
    уведомление не было пустым.

    Возвращает True при успешной отправке, False при пропуске (нет токена/чата)
    или ошибке. Ошибки не пробрасываются: уведомление — побочный эффект и не
    должно ронять исполнение правила.
    """
    bot_token = _normalize_str(bot_token)
    chat_id = _normalize_str(chat_id)
    if not bot_token or not chat_id:
        logger.debug(
            "admin_notification_skipped_missing_config",
            agent_name=agent_name,
            session_id=session_id,
            has_token=bool(bot_token),
            has_chat_id=bool(chat_id),
        )
        return False

    parts: list[str] = [_normalize_str(message) or "Уведомление от агента"]
    parts.append(f"Агент: {agent_name}")
    parts.append(f"Сессия: {session_id}")
    if last_client_message:
        snippet = last_client_message.strip()
        if len(snippet) > 400:
            snippet = snippet[:400] + "..."
        parts.append(f"\nСообщение клиента:\n{snippet}")

    try:
        await send_telegram_message(
            bot_token=bot_token,
            chat_id=chat_id,
            text="\n".join(parts),
            timeout_seconds=5,
        )
        logger.info(
            "admin_notification_sent",
            agent_name=agent_name,
            session_id=session_id,
        )
        return True
    except (TelegramWebhookError, ValueError) as exc:
        logger.warning(
            "admin_notification_failed",
            agent_name=agent_name,
            session_id=session_id,
            error=str(exc),
        )
        return False
