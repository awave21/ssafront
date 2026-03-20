from __future__ import annotations

from typing import Final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.channel import Channel
from app.services.ops_alerts import send_wappi_balance_alert
from app.services.wappi.client import (
    WappiAuthQrResult,
    WappiClient,
    WappiClientError,
    WappiPlatform,
    WappiProfileCreateResult,
    WappiProfileDeleteResult,
)

logger = structlog.get_logger(__name__)

_CHANNEL_PLATFORM_MAP: Final[dict[str, WappiPlatform]] = {
    "whatsapp": WappiPlatform.WHATSAPP,
    "telegram_phone": WappiPlatform.TELEGRAM_PHONE,
    "max": WappiPlatform.MAX,
}

_INSUFFICIENT_BALANCE_MARKERS: Final[tuple[str, ...]] = (
    "не хватает денег на балансе",
    "insufficient balance",
    "not enough balance",
)


class ChannelProfileBindingError(Exception):
    """Базовая ошибка сервиса привязки профилей канала."""


class ChannelProfileConfigError(ChannelProfileBindingError):
    """Некорректная конфигурация WAPPI."""


class ChannelProfileUnsupportedTypeError(ChannelProfileBindingError):
    """Тип канала не поддерживает WAPPI-профили."""


class ChannelProfileAlreadyBoundError(ChannelProfileBindingError):
    """У канала уже есть привязанный профиль."""


class ChannelProfileNotBoundError(ChannelProfileBindingError):
    """У канала нет привязанного профиля."""


class ChannelProfileExternalError(ChannelProfileBindingError):
    """Ошибка внешнего вызова в WAPPI API."""


def _resolve_wappi_platform(channel_type: str) -> WappiPlatform:
    platform = _CHANNEL_PLATFORM_MAP.get(channel_type)
    if platform is None:
        raise ChannelProfileUnsupportedTypeError(
            f"Тип канала '{channel_type}' не поддерживает подключение номера"
        )
    return platform


def build_wappi_client(settings: Settings | None = None) -> WappiClient:
    cfg = settings or get_settings()
    token = (cfg.wappi_api_token or "").strip()
    if not token:
        raise ChannelProfileConfigError("Не задан токен сервиса подключения канала")
    return WappiClient(
        base_url=cfg.wappi_base_url,
        api_token=token,
        timeout_seconds=cfg.wappi_timeout_seconds,
        retry_attempts=cfg.wappi_retry_attempts,
        retry_min_seconds=cfg.wappi_retry_min_seconds,
        retry_max_seconds=cfg.wappi_retry_max_seconds,
    )


def _normalize_error_text_for_match(error_text: str) -> str:
    normalized = (error_text or "").strip().lower()
    if not normalized:
        return ""
    try:
        decoded = normalized.encode("utf-8").decode("unicode_escape").lower()
    except Exception:  # noqa: BLE001
        decoded = normalized
    return f"{normalized}\n{decoded}"


def _is_insufficient_balance_error(error_text: str) -> bool:
    normalized = _normalize_error_text_for_match(error_text)
    return any(marker in normalized for marker in _INSUFFICIENT_BALANCE_MARKERS)


async def bind_profile_to_channel(
    *,
    db: AsyncSession,
    channel: Channel,
    profile_name: str,
    webhook_url: str | None = None,
    tariff_id: int | None = None,
    promo_code: str | None = None,
    client: WappiClient | None = None,
) -> WappiProfileCreateResult:
    if channel.wappi_profile_id:
        raise ChannelProfileAlreadyBoundError(
            f"Канал уже привязан к профилю {channel.wappi_profile_id}"
        )
    platform = _resolve_wappi_platform(channel.type)
    settings = get_settings()
    wappi_client = client or build_wappi_client(settings)
    effective_tariff_id = tariff_id if tariff_id is not None else settings.wappi_profile_tariff_id
    effective_promo_code = promo_code if promo_code is not None else settings.wappi_profile_promo_code
    try:
        result = await wappi_client.create_profile(
            platform=platform,
            name=profile_name,
            webhook_url=webhook_url,
        )
    except WappiClientError as exc:
        raise ChannelProfileExternalError(str(exc)) from exc

    try:
        await wappi_client.add_days_from_balance(
            profile_uuid=result.profile_id,
            tariff_id=effective_tariff_id,
            profile_ids=[result.profile_id],
            code=effective_promo_code,
        )
    except WappiClientError as exc:
        payment_error_text = str(exc)
        if _is_insufficient_balance_error(payment_error_text):
            await send_wappi_balance_alert(
                channel_id=str(channel.id),
                channel_type=channel.type,
                profile_id=result.profile_id,
                tariff_id=effective_tariff_id,
                error_text=payment_error_text,
            )
        cleanup_error: str | None = None
        try:
            await wappi_client.delete_profile(
                platform=platform,
                profile_id=result.profile_id,
            )
        except WappiClientError as cleanup_exc:
            cleanup_error = str(cleanup_exc)
            logger.error(
                "channel_wappi_profile_cleanup_failed",
                channel_id=str(channel.id),
                channel_type=channel.type,
                profile_id=result.profile_id,
                error=cleanup_error,
            )
        detail = "Не удалось оплатить профиль после создания"
        if cleanup_error:
            detail = f"{detail}; delete profile failed: {cleanup_error}"
        raise ChannelProfileExternalError(detail) from exc

    channel.wappi_profile_id = result.profile_id
    channel.phone_is_authorized = False
    await db.flush()
    logger.info(
        "channel_wappi_profile_bound",
        channel_id=str(channel.id),
        channel_type=channel.type,
        profile_id=result.profile_id,
        tariff_id=effective_tariff_id,
    )
    return result


async def unbind_profile_from_channel(
    *,
    db: AsyncSession,
    channel: Channel,
    client: WappiClient | None = None,
    ignore_missing: bool = False,
) -> WappiProfileDeleteResult | None:
    if not channel.wappi_profile_id:
        if ignore_missing:
            channel.phone_is_authorized = False
            await db.flush()
            return None
        raise ChannelProfileNotBoundError("У канала отсутствует привязанный профиль")

    platform = _resolve_wappi_platform(channel.type)
    profile_id = channel.wappi_profile_id
    wappi_client = client or build_wappi_client()
    try:
        result = await wappi_client.delete_profile(
            platform=platform,
            profile_id=profile_id,
        )
    except WappiClientError as exc:
        raise ChannelProfileExternalError(str(exc)) from exc

    channel.wappi_profile_id = None
    channel.phone_is_authorized = False
    await db.flush()
    logger.info(
        "channel_wappi_profile_unbound",
        channel_id=str(channel.id),
        channel_type=channel.type,
        profile_id=profile_id,
    )
    return result


async def request_channel_auth_qr(
    *,
    channel: Channel,
    client: WappiClient | None = None,
) -> WappiAuthQrResult:
    profile_id = (channel.wappi_profile_id or "").strip()
    if not profile_id:
        raise ChannelProfileNotBoundError("Канал еще не готов к авторизации")

    platform = _resolve_wappi_platform(channel.type)
    wappi_client = client or build_wappi_client()
    try:
        qr_result = await wappi_client.get_auth_qr(
            platform=platform,
            profile_id=profile_id,
        )
    except WappiClientError as exc:
        raise ChannelProfileExternalError(str(exc)) from exc

    logger.info(
        "channel_phone_auth_qr_requested",
        channel_id=str(channel.id),
        channel_type=channel.type,
        profile_id=profile_id,
        qr_uuid=qr_result.uuid,
    )
    return qr_result
