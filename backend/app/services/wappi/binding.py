from __future__ import annotations

from typing import Any, Final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.channel import Channel
from app.services.ops_alerts import send_wappi_balance_alert
from app.services.wappi.client import (
    WappiAuth2FAResult,
    WappiAuthQrResult,
    WappiClient,
    WappiClientError,
    WappiPlatform,
    WappiProfileCreateResult,
    WappiProfileLogoutResult,
)

logger = structlog.get_logger(__name__)
wappi_action_logger = structlog.get_logger("webhooks.wappi")

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
_ALREADY_AUTHORIZED_MARKERS: Final[tuple[str, ...]] = (
    "you are already authorized",
    "already authorized",
    "already authorised",
    "already logged in",
    "уже авториз",
    "уже подключен",
)
_CHANNEL_AUTH_2FA_TYPES: Final[set[str]] = {"telegram_phone", "max"}


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

    def __init__(
        self,
        message: str,
        *,
        profile_id: str | None = None,
        payment_error: str | None = None,
    ) -> None:
        super().__init__(message)
        self.profile_id = profile_id
        self.payment_error = payment_error


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


def _is_already_authorized_error(error_text: str) -> bool:
    normalized = _normalize_error_text_for_match(error_text)
    return any(marker in normalized for marker in _ALREADY_AUTHORIZED_MARKERS)


def _build_payment_failure_detail(*, profile_id: str, cleanup_error: str | None) -> str:
    detail = f"Не удалось оплатить профиль после создания (profile_id={profile_id})"
    if cleanup_error:
        return f"{detail}; delete profile failed: {cleanup_error}"
    return detail


def _normalize_optional_str(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    return normalized


def _mask_sensitive_value(value: str | None) -> str | None:
    normalized = _normalize_optional_str(value)
    if normalized is None:
        return None
    if len(normalized) <= 4:
        return "*" * len(normalized)
    return f"{normalized[:2]}***{normalized[-2:]}"


def _build_wappi_action_context(*, channel: Channel, platform: WappiPlatform) -> dict[str, str]:
    return {
        "channel_id": str(channel.id),
        "channel_type": channel.type,
        "platform": platform.value,
    }


def _build_create_request_payload(*, profile_name: str, webhook_url: str | None) -> dict[str, str]:
    payload: dict[str, str] = {"name": profile_name}
    normalized_webhook_url = _normalize_optional_str(webhook_url)
    if normalized_webhook_url is not None:
        payload["webhook_url"] = normalized_webhook_url
    return payload


def _build_add_days_request_payload(
    *,
    profile_id: str,
    tariff_id: int,
    promo_code: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "profile_uuid": profile_id,
        "tariff_id": tariff_id,
    }
    masked_code = _mask_sensitive_value(promo_code)
    if masked_code is not None:
        payload["code_masked"] = masked_code
    return payload


def _build_auth_qr_request_payload(*, profile_id: str) -> dict[str, str]:
    return {"profile_id": profile_id}


def _build_logout_request_payload(*, profile_id: str) -> dict[str, str]:
    return {"profile_id": profile_id}


def _build_auth_2fa_request_payload(*, profile_id: str, pwd_code: str) -> dict[str, str | int]:
    return {
        "profile_id": profile_id,
        "pwd_code_masked": _mask_sensitive_value(pwd_code) or "***",
        "pwd_code_length": len(pwd_code),
    }


def _truncate_for_log(value: str, *, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}..."


def _sanitize_qr_raw_payload(raw_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if raw_payload is None:
        return None
    sanitized = dict(raw_payload)
    for key in ("qrCode", "qr_code"):
        value = sanitized.get(key)
        if isinstance(value, str):
            sanitized[f"{key}_length"] = len(value)
            sanitized[key] = _truncate_for_log(value, max_length=160)
    detail_value = sanitized.get("detail")
    if isinstance(detail_value, str) and len(detail_value) > 500:
        sanitized["detail_length"] = len(detail_value)
        sanitized["detail"] = _truncate_for_log(detail_value, max_length=500)
    return sanitized


def _build_auth_qr_response_payload(*, qr_result: WappiAuthQrResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": qr_result.status,
        "detail": qr_result.detail,
        "requires_2fa": qr_result.requires_2fa,
        "uuid": qr_result.uuid,
        "time": qr_result.time,
        "timestamp": qr_result.timestamp,
        "qr_code_length": len(qr_result.qr_code),
    }
    sanitized_raw = _sanitize_qr_raw_payload(qr_result.raw)
    if sanitized_raw is not None:
        payload["raw"] = sanitized_raw
    else:
        payload["qr_code_preview"] = _truncate_for_log(qr_result.qr_code, max_length=160)
    return payload


def _build_auth_2fa_response_payload(*, auth_2fa_result: WappiAuth2FAResult) -> dict[str, Any]:
    return auth_2fa_result.raw or {
        "status": auth_2fa_result.status,
        "detail": auth_2fa_result.detail,
        "uuid": auth_2fa_result.uuid,
        "time": auth_2fa_result.time,
        "timestamp": auth_2fa_result.timestamp,
    }


def _build_logout_response_payload(*, logout_result: WappiProfileLogoutResult) -> dict[str, Any]:
    return logout_result.raw or {
        "status": logout_result.status,
        "detail": logout_result.detail,
        "uuid": logout_result.uuid,
        "time": logout_result.time,
        "timestamp": logout_result.timestamp,
    }


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
    action_context = _build_wappi_action_context(channel=channel, platform=platform)
    create_request_payload = _build_create_request_payload(
        profile_name=profile_name,
        webhook_url=webhook_url,
    )
    wappi_action_logger.info(
        "channel_wappi_profile_create_request",
        **action_context,
        request_payload=create_request_payload,
    )
    try:
        result = await wappi_client.create_profile(
            platform=platform,
            name=profile_name,
            webhook_url=webhook_url,
        )
    except WappiClientError as exc:
        wappi_action_logger.warning(
            "channel_wappi_profile_create_failed",
            **action_context,
            request_payload=create_request_payload,
            error=str(exc),
        )
        raise ChannelProfileExternalError(str(exc)) from exc

    wappi_action_logger.info(
        "channel_wappi_profile_create_response",
        **action_context,
        profile_id=result.profile_id,
        response_payload=result.raw
        or {
            "profile_id": result.profile_id,
            "status": result.status,
            "detail": result.detail,
            "time": result.time,
            "timestamp": result.timestamp,
        },
    )

    payment_request_payload = _build_add_days_request_payload(
        profile_id=result.profile_id,
        tariff_id=effective_tariff_id,
        promo_code=effective_promo_code,
    )
    wappi_action_logger.info(
        "channel_wappi_profile_payment_request",
        **action_context,
        profile_id=result.profile_id,
        request_payload=payment_request_payload,
    )
    try:
        payment_result = await wappi_client.add_days_from_balance(
            profile_uuid=result.profile_id,
            tariff_id=effective_tariff_id,
            code=effective_promo_code,
        )
    except WappiClientError as exc:
        payment_error_text = str(exc)
        wappi_action_logger.warning(
            "channel_wappi_profile_payment_failed",
            **action_context,
            profile_id=result.profile_id,
            request_payload=payment_request_payload,
            error=payment_error_text,
        )
        logger.warning(
            "channel_wappi_profile_payment_failed",
            channel_id=str(channel.id),
            channel_type=channel.type,
            profile_id=result.profile_id,
            tariff_id=effective_tariff_id,
            error=payment_error_text,
        )
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
        detail = _build_payment_failure_detail(
            profile_id=result.profile_id,
            cleanup_error=cleanup_error,
        )
        raise ChannelProfileExternalError(
            detail,
            profile_id=result.profile_id,
            payment_error=payment_error_text,
        ) from exc

    wappi_action_logger.info(
        "channel_wappi_profile_payment_response",
        **action_context,
        profile_id=result.profile_id,
        response_payload=payment_result.raw
        or {
            "status": payment_result.status,
            "detail": payment_result.detail,
            "time": payment_result.time,
            "timestamp": payment_result.timestamp,
        },
    )

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
) -> WappiProfileLogoutResult | None:
    if not channel.wappi_profile_id:
        if ignore_missing:
            channel.phone_is_authorized = False
            await db.flush()
            return None
        raise ChannelProfileNotBoundError("У канала отсутствует привязанный профиль")

    platform = _resolve_wappi_platform(channel.type)
    profile_id = channel.wappi_profile_id
    wappi_client = client or build_wappi_client()
    action_context = _build_wappi_action_context(channel=channel, platform=platform)
    logout_request_payload = _build_logout_request_payload(profile_id=profile_id)
    wappi_action_logger.info(
        "channel_wappi_profile_logout_request",
        **action_context,
        profile_id=profile_id,
        request_payload=logout_request_payload,
    )
    try:
        result = await wappi_client.logout_profile(
            platform=platform,
            profile_id=profile_id,
        )
    except WappiClientError as exc:
        wappi_action_logger.warning(
            "channel_wappi_profile_logout_failed",
            **action_context,
            profile_id=profile_id,
            request_payload=logout_request_payload,
            error=str(exc),
        )
        raise ChannelProfileExternalError(str(exc), profile_id=profile_id) from exc

    channel.phone_is_authorized = False
    await db.flush()
    wappi_action_logger.info(
        "channel_wappi_profile_logout_response",
        **action_context,
        profile_id=profile_id,
        response_payload=_build_logout_response_payload(logout_result=result),
    )
    logger.info(
        "channel_wappi_profile_logged_out",
        channel_id=str(channel.id),
        channel_type=channel.type,
        profile_id=profile_id,
    )
    return result


async def request_channel_auth_qr(
    *,
    db: AsyncSession | None = None,
    channel: Channel,
    client: WappiClient | None = None,
) -> WappiAuthQrResult:
    profile_id = (channel.wappi_profile_id or "").strip()
    if not profile_id:
        raise ChannelProfileNotBoundError("Канал еще не готов к авторизации")

    platform = _resolve_wappi_platform(channel.type)
    wappi_client = client or build_wappi_client()
    action_context = _build_wappi_action_context(channel=channel, platform=platform)
    qr_request_payload = _build_auth_qr_request_payload(profile_id=profile_id)
    wappi_action_logger.info(
        "channel_wappi_auth_qr_request",
        **action_context,
        profile_id=profile_id,
        request_payload=qr_request_payload,
    )
    try:
        qr_result = await wappi_client.get_auth_qr(
            platform=platform,
            profile_id=profile_id,
        )
    except WappiClientError as exc:
        error_text = str(exc)
        if _is_already_authorized_error(error_text):
            channel.phone_is_authorized = True
            if db is not None:
                await db.flush()
            qr_result = WappiAuthQrResult(
                status="done",
                qr_code="",
                detail="already_authorized",
                requires_2fa=False,
                uuid=profile_id,
                raw={
                    "status": "done",
                    "detail": "already_authorized",
                    "uuid": profile_id,
                },
            )
            wappi_action_logger.info(
                "channel_wappi_auth_qr_already_authorized",
                **action_context,
                profile_id=profile_id,
                request_payload=qr_request_payload,
                response_payload=qr_result.raw,
            )
            logger.info(
                "channel_phone_auth_already_authorized",
                channel_id=str(channel.id),
                channel_type=channel.type,
                profile_id=profile_id,
            )
            return qr_result
        wappi_action_logger.warning(
            "channel_wappi_auth_qr_failed",
            **action_context,
            profile_id=profile_id,
            request_payload=qr_request_payload,
            error=error_text,
        )
        raise ChannelProfileExternalError(error_text) from exc

    wappi_action_logger.info(
        "channel_wappi_auth_qr_response",
        **action_context,
        profile_id=profile_id,
        response_payload=_build_auth_qr_response_payload(qr_result=qr_result),
    )
    if qr_result.requires_2fa:
        wappi_action_logger.info(
            "channel_wappi_auth_qr_requires_2fa",
            **action_context,
            profile_id=profile_id,
            response_payload=qr_result.raw
            or {
                "status": qr_result.status,
                "detail": qr_result.detail,
                "uuid": qr_result.uuid,
                "time": qr_result.time,
                "timestamp": qr_result.timestamp,
            },
        )
    logger.info(
        "channel_phone_auth_qr_requested",
        channel_id=str(channel.id),
        channel_type=channel.type,
        profile_id=profile_id,
        qr_uuid=qr_result.uuid,
        requires_2fa=qr_result.requires_2fa,
    )
    return qr_result


async def submit_channel_auth_2fa(
    *,
    channel: Channel,
    pwd_code: str,
    client: WappiClient | None = None,
) -> WappiAuth2FAResult:
    profile_id = (channel.wappi_profile_id or "").strip()
    if not profile_id:
        raise ChannelProfileNotBoundError("Канал еще не готов к авторизации")
    if channel.type not in _CHANNEL_AUTH_2FA_TYPES:
        raise ChannelProfileUnsupportedTypeError(
            f"2FA авторизация недоступна для типа канала '{channel.type}'"
        )

    platform = _resolve_wappi_platform(channel.type)
    wappi_client = client or build_wappi_client()
    action_context = _build_wappi_action_context(channel=channel, platform=platform)
    auth_2fa_request_payload = _build_auth_2fa_request_payload(
        profile_id=profile_id,
        pwd_code=pwd_code,
    )
    wappi_action_logger.info(
        "channel_wappi_auth_2fa_request",
        **action_context,
        profile_id=profile_id,
        request_payload=auth_2fa_request_payload,
    )
    try:
        auth_2fa_result = await wappi_client.submit_auth_2fa(
            platform=platform,
            profile_id=profile_id,
            pwd_code=pwd_code,
        )
    except WappiClientError as exc:
        wappi_action_logger.warning(
            "channel_wappi_auth_2fa_failed",
            **action_context,
            profile_id=profile_id,
            request_payload=auth_2fa_request_payload,
            error=str(exc),
        )
        raise ChannelProfileExternalError(str(exc), profile_id=profile_id) from exc

    wappi_action_logger.info(
        "channel_wappi_auth_2fa_response",
        **action_context,
        profile_id=profile_id,
        response_payload=_build_auth_2fa_response_payload(auth_2fa_result=auth_2fa_result),
    )
    logger.info(
        "channel_phone_auth_2fa_submitted",
        channel_id=str(channel.id),
        channel_type=channel.type,
        profile_id=profile_id,
        status=auth_2fa_result.status,
        detail=auth_2fa_result.detail,
    )
    return auth_2fa_result
