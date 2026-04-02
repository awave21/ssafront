from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urljoin

import httpx
import structlog
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


class WappiClientError(Exception):
    """Ошибка взаимодействия с WAPPI API."""


class WappiPlatform(str, Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM_PHONE = "telegram"
    MAX = "max"


@dataclass(frozen=True)
class WappiProfileCreateResult:
    profile_id: str
    status: str
    detail: str | None = None
    time: str | None = None
    timestamp: int | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class WappiWebhookUrlSetResult:
    status: str
    detail: str | None = None
    task_id: str | None = None
    time: str | None = None
    timestamp: int | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class WappiWebhookTypesSetResult:
    status: str
    detail: str | None = None
    task_id: str | None = None
    time: str | None = None
    timestamp: int | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class WappiProfileDeleteResult:
    status: str
    detail: str | None = None
    time: str | None = None
    timestamp: int | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class WappiProfileLogoutResult:
    status: str
    detail: str | None = None
    uuid: str | None = None
    time: str | None = None
    timestamp: int | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class WappiBalanceAddDaysResult:
    status: str
    detail: str | None = None
    time: str | None = None
    timestamp: int | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class WappiAuthQrResult:
    status: str
    qr_code: str
    detail: str | None = None
    requires_2fa: bool = False
    uuid: str | None = None
    time: str | None = None
    timestamp: int | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class WappiAuth2FAResult:
    status: str
    detail: str | None = None
    uuid: str | None = None
    time: str | None = None
    timestamp: int | None = None


@dataclass(frozen=True)
class WappiSyncMessageSendResult:
    status: str
    detail: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class WappiAsyncMessageSendResult:
    status: str
    detail: str | None = None
    task_id: str | None = None
    time: str | None = None
    timestamp: int | None = None
    uuid: str | None = None
    command_start: str | None = None
    command_end: str | None = None
    raw: dict[str, Any] | None = None


_CREATE_PROFILE_PATHS: dict[WappiPlatform, str] = {
    WappiPlatform.WHATSAPP: "/api/profile/add",
    WappiPlatform.TELEGRAM_PHONE: "/tapi/profile/add",
    WappiPlatform.MAX: "/maxapi/profile/add",
}
_SET_WEBHOOK_URL_PATHS: dict[WappiPlatform, str] = {
    WappiPlatform.WHATSAPP: "/api/webhook/url/set",
    WappiPlatform.TELEGRAM_PHONE: "/tapi/webhook/url/set",
    WappiPlatform.MAX: "/maxapi/webhook/url/set",
}
_SET_WEBHOOK_TYPES_PATHS: dict[WappiPlatform, str] = {
    WappiPlatform.WHATSAPP: "/api/webhook/types/set",
    WappiPlatform.TELEGRAM_PHONE: "/tapi/webhook/types/set",
    WappiPlatform.MAX: "/maxapi/webhook/types/set",
}

_DELETE_PROFILE_PATHS: dict[WappiPlatform, str] = {
    WappiPlatform.WHATSAPP: "/api/profile/delete",
    WappiPlatform.TELEGRAM_PHONE: "/tapi/profile/delete",
    WappiPlatform.MAX: "/maxapi/profile/delete",
}
_LOGOUT_PROFILE_PATHS: dict[WappiPlatform, str] = {
    WappiPlatform.WHATSAPP: "/api/profile/logout",
    WappiPlatform.TELEGRAM_PHONE: "/tapi/profile/logout",
    WappiPlatform.MAX: "/maxapi/profile/logout",
}

_WEBHOOK_SUPPORTED_PLATFORMS: set[WappiPlatform] = {
    WappiPlatform.WHATSAPP,
    WappiPlatform.TELEGRAM_PHONE,
    WappiPlatform.MAX,
}
_AUTH_QR_PATHS: dict[WappiPlatform, str] = {
    WappiPlatform.WHATSAPP: "/api/sync/qr/get",
    WappiPlatform.TELEGRAM_PHONE: "/tapi/sync/auth/qr",
    WappiPlatform.MAX: "/maxapi/sync/auth/qr",
}
_AUTH_2FA_PATHS: dict[WappiPlatform, str] = {
    WappiPlatform.TELEGRAM_PHONE: "/tapi/sync/auth/2fa",
    WappiPlatform.MAX: "/maxapi/sync/auth/2fa",
}
_TAPI_SYNC_MESSAGE_SEND_PATH = "/tapi/sync/message/send"
_TAPI_ASYNC_MESSAGE_SEND_PATH = "/tapi/async/message/send"
_API_ASYNC_MESSAGE_SEND_PATH = "/api/async/message/send"
_MAXAPI_SYNC_MESSAGE_SEND_PATH = "/maxapi/sync/message/send"
_MAXAPI_ASYNC_MESSAGE_SEND_PATH = "/maxapi/async/message/send"
_BALANCE_ADD_DAYS_PATH = "/payments/balance/add_days"
_AVAILABLE_TARIFF_IDS = {1, 2, 3, 4}
_AUTH_2FA_REQUIRED_MARKERS = {
    "2fa",
    "need2fa",
    "auth2fa",
    "twofactorrequired",
    "passwordrequired",
    "cloudpasswordrequired",
}
_LOGOUT_SUCCESS_DETAIL_MARKERS = (
    "logout",
    "logouted",
    "logout success",
    "ok",
    "success",
)


def _normalize_base_url(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        raise WappiClientError("Service base URL is required")
    if not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"
    return normalized


def _is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return False


def _to_int_or_none(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _normalize_timeout_param(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise WappiClientError(f"{field_name} must be an integer")
    if isinstance(value, int):
        normalized = value
    elif isinstance(value, str) and value.strip().isdigit():
        normalized = int(value.strip())
    else:
        raise WappiClientError(f"{field_name} must be an integer")
    if normalized < 0:
        raise WappiClientError(f"{field_name} must be greater than or equal to 0")
    return normalized


def _is_dashboard_payment_redirect(value: str) -> bool:
    normalized = (value or "").strip()
    if not normalized:
        return False
    return normalized.startswith("/dashboard/")


def _is_2fa_required_detail(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return False
    compact = "".join(ch for ch in normalized if ch.isalnum())
    if compact in _AUTH_2FA_REQUIRED_MARKERS:
        return True
    normalized_words = normalized.replace("-", " ").replace("_", " ")
    return (
        "two factor" in normalized_words
        or "password required" in normalized_words
        or "cloud password" in normalized_words
    )


def _is_logout_success_detail(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in _LOGOUT_SUCCESS_DETAIL_MARKERS)


def _normalize_qr_code(raw_value: str) -> str:
    value = "".join(raw_value.split())
    if not value:
        return ""
    if value.startswith("data:"):
        return value
    if value.startswith(("http://", "https://")):
        return value

    # Telegram/MAX могут вернуть только base64-строку без data URI.
    image_type = "image/png"
    if value.startswith("/9j/"):
        image_type = "image/jpeg"
    elif value.startswith("R0lGOD"):
        image_type = "image/gif"
    elif value.startswith("UklGR"):
        image_type = "image/webp"
    return f"data:{image_type};base64,{value}"


class WappiClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_token: str,
        timeout_seconds: float = 15.0,
        retry_attempts: int = 2,
        retry_min_seconds: float = 0.5,
        retry_max_seconds: float = 4.0,
    ) -> None:
        token = (api_token or "").strip()
        if not token:
            raise WappiClientError("Service API token is required")
        self._base_url = _normalize_base_url(base_url)
        self._api_token = token
        self._timeout_seconds = timeout_seconds
        self._retry_attempts = max(retry_attempts, 0)
        self._retry_min_seconds = max(retry_min_seconds, 0.0)
        self._retry_max_seconds = max(retry_max_seconds, self._retry_min_seconds)

    async def create_profile(
        self,
        *,
        platform: WappiPlatform,
        name: str,
        webhook_url: str | None = None,
    ) -> WappiProfileCreateResult:
        normalized_name = name.strip()
        if not normalized_name:
            raise WappiClientError("Profile name is required")
        params: dict[str, Any] = {"name": normalized_name}
        if webhook_url and platform in _WEBHOOK_SUPPORTED_PLATFORMS:
            params["webhook_url"] = webhook_url
        payload = await self._request_json(
            method="POST",
            path=_CREATE_PROFILE_PATHS[platform],
            params=params,
        )
        profile_id = str(payload.get("profile_id") or "").strip()
        if not profile_id:
            raise WappiClientError("Create profile response is missing profile_id")
        return WappiProfileCreateResult(
            profile_id=profile_id,
            status=str(payload.get("status") or "done"),
            detail=str(payload.get("detail")) if payload.get("detail") is not None else None,
            time=str(payload.get("time")) if payload.get("time") is not None else None,
            timestamp=_to_int_or_none(payload.get("timestamp")),
            raw=payload,
        )

    async def set_webhook_url(
        self,
        *,
        platform: WappiPlatform,
        profile_id: str,
        webhook_url: str,
        auth: str | None = None,
    ) -> WappiWebhookUrlSetResult:
        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise WappiClientError("profile_id is required")
        normalized_webhook_url = webhook_url.strip()
        if not normalized_webhook_url:
            raise WappiClientError("webhook_url is required")
        normalized_auth = (auth or "").strip() or None

        request_params: dict[str, Any] = {
            "profile_id": normalized_profile_id,
            "url": normalized_webhook_url,
        }
        if normalized_auth is not None:
            request_params["auth"] = normalized_auth

        payload = await self._request_json_or_text(
            method="POST",
            path=_SET_WEBHOOK_URL_PATHS[platform],
            params=request_params,
            accept="application/json, text/plain",
        )
        status = str(payload.get("status")).strip() if payload.get("status") is not None else ""
        detail = str(payload.get("detail")).strip() if payload.get("detail") is not None else None
        if not status:
            raise WappiClientError("Set webhook url response is missing status")
        if status.lower() not in {"done", "ok", "success"}:
            raise WappiClientError(detail or f"Set webhook url request returned status '{status}'")

        return WappiWebhookUrlSetResult(
            status=status,
            detail=detail,
            task_id=str(payload.get("task_id")).strip() if payload.get("task_id") is not None else None,
            time=str(payload.get("time")) if payload.get("time") is not None else None,
            timestamp=_to_int_or_none(payload.get("timestamp")),
            raw=payload,
        )

    async def set_webhook_types(
        self,
        *,
        platform: WappiPlatform,
        profile_id: str,
        webhook_types: list[str],
    ) -> WappiWebhookTypesSetResult:
        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise WappiClientError("profile_id is required")

        normalized_types: list[str] = []
        seen_types: set[str] = set()
        for raw_type in webhook_types:
            normalized_type = str(raw_type or "").strip()
            if not normalized_type or normalized_type in seen_types:
                continue
            normalized_types.append(normalized_type)
            seen_types.add(normalized_type)
        if not normalized_types:
            raise WappiClientError("At least one webhook type is required")

        payload = await self._request_json_or_text(
            method="POST",
            path=_SET_WEBHOOK_TYPES_PATHS[platform],
            params={"profile_id": normalized_profile_id},
            json=normalized_types,
            accept="application/json, text/plain",
        )
        status = str(payload.get("status")).strip() if payload.get("status") is not None else ""
        detail = str(payload.get("detail")).strip() if payload.get("detail") is not None else None
        if not status:
            raise WappiClientError("Set webhook types response is missing status")
        if status.lower() not in {"done", "ok", "success"}:
            raise WappiClientError(detail or f"Set webhook types request returned status '{status}'")

        return WappiWebhookTypesSetResult(
            status=status,
            detail=detail,
            task_id=str(payload.get("task_id")).strip() if payload.get("task_id") is not None else None,
            time=str(payload.get("time")) if payload.get("time") is not None else None,
            timestamp=_to_int_or_none(payload.get("timestamp")),
            raw=payload,
        )

    async def delete_profile(
        self,
        *,
        platform: WappiPlatform,
        profile_id: str,
    ) -> WappiProfileDeleteResult:
        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise WappiClientError("profile_id is required")
        payload = await self._request_json(
            method="POST",
            path=_DELETE_PROFILE_PATHS[platform],
            params={"profile_id": normalized_profile_id},
        )
        return WappiProfileDeleteResult(
            status=str(payload.get("status") or "done"),
            detail=str(payload.get("detail")) if payload.get("detail") is not None else None,
            time=str(payload.get("time")) if payload.get("time") is not None else None,
            timestamp=_to_int_or_none(payload.get("timestamp")),
            raw=payload,
        )

    async def logout_profile(
        self,
        *,
        platform: WappiPlatform,
        profile_id: str,
    ) -> WappiProfileLogoutResult:
        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise WappiClientError("profile_id is required")

        payload = await self._request_json_or_text(
            method="GET",
            path=_LOGOUT_PROFILE_PATHS[platform],
            params={"profile_id": normalized_profile_id},
        )
        status = str(payload.get("status")).strip() if payload.get("status") is not None else ""
        detail = str(payload.get("detail")).strip() if payload.get("detail") is not None else ""
        if status:
            if status.lower() not in {"done", "ok", "success"}:
                raise WappiClientError(detail or f"Logout request returned status '{status}'")
        elif detail:
            if not _is_logout_success_detail(detail):
                raise WappiClientError(detail)
        else:
            raise WappiClientError("Logout response is missing status and detail")

        return WappiProfileLogoutResult(
            status=status or "done",
            detail=detail or None,
            uuid=str(payload.get("uuid")).strip() if payload.get("uuid") is not None else None,
            time=str(payload.get("time")) if payload.get("time") is not None else None,
            timestamp=_to_int_or_none(payload.get("timestamp")),
            raw=payload,
        )

    async def add_days_from_balance(
        self,
        *,
        profile_uuid: str,
        tariff_id: int,
        profile_ids: list[str] | None = None,
        code: str | None = None,
    ) -> WappiBalanceAddDaysResult:
        normalized_profile_uuid = profile_uuid.strip()
        if not normalized_profile_uuid:
            raise WappiClientError("profile_uuid is required")
        if tariff_id not in _AVAILABLE_TARIFF_IDS:
            raise WappiClientError("tariff_id must be one of: 1, 2, 3, 4")

        payload = {
            "profile_uuid": normalized_profile_uuid,
            "tariff_id": tariff_id,
        }
        normalized_profile_ids: list[str] = []
        for value in profile_ids or []:
            normalized = str(value).strip()
            if normalized:
                normalized_profile_ids.append(normalized)
        if normalized_profile_ids:
            if normalized_profile_uuid not in normalized_profile_ids:
                normalized_profile_ids.insert(0, normalized_profile_uuid)
            payload["profile_ids"] = normalized_profile_ids
        normalized_code = (code or "").strip()
        if normalized_code:
            payload["code"] = normalized_code

        response_payload = await self._request_json_or_text(
            method="POST",
            path=_BALANCE_ADD_DAYS_PATH,
            json=payload,
        )
        status = str(response_payload.get("status")).strip() if response_payload.get("status") is not None else ""
        detail = str(response_payload.get("detail")).strip() if response_payload.get("detail") is not None else ""
        if status:
            if status.lower() not in {"done", "ok", "success"}:
                raise WappiClientError(detail or f"Balance payment request returned status '{status}'")
        elif detail:
            if not _is_dashboard_payment_redirect(detail):
                raise WappiClientError(detail)
        else:
            raise WappiClientError("Balance payment response is missing status and detail")

        return WappiBalanceAddDaysResult(
            status=status or "done",
            detail=detail or None,
            time=str(response_payload.get("time")) if response_payload.get("time") is not None else None,
            timestamp=_to_int_or_none(response_payload.get("timestamp")),
            raw=response_payload,
        )

    async def get_auth_qr(
        self,
        *,
        platform: WappiPlatform,
        profile_id: str,
    ) -> WappiAuthQrResult:
        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise WappiClientError("profile_id is required")

        payload = await self._request_json(
            method="GET",
            path=_AUTH_QR_PATHS[platform],
            params={"profile_id": normalized_profile_id},
        )
        status = str(payload.get("status") or "done")
        detail = str(payload.get("detail")).strip() if payload.get("detail") is not None else None
        if _is_2fa_required_detail(detail):
            return WappiAuthQrResult(
                status=status,
                qr_code="",
                detail=detail,
                requires_2fa=True,
                uuid=str(payload.get("uuid")) if payload.get("uuid") is not None else None,
                time=str(payload.get("time")) if payload.get("time") is not None else None,
                timestamp=_to_int_or_none(payload.get("timestamp")),
                raw=payload,
            )

        qr_raw = payload.get("qrCode") or payload.get("qr_code") or payload.get("detail")
        qr_code = _normalize_qr_code(str(qr_raw or ""))
        if not qr_code:
            raise WappiClientError("QR code is missing in service response")

        return WappiAuthQrResult(
            status=status,
            qr_code=qr_code,
            detail=detail,
            requires_2fa=False,
            uuid=str(payload.get("uuid")) if payload.get("uuid") is not None else None,
            time=str(payload.get("time")) if payload.get("time") is not None else None,
            timestamp=_to_int_or_none(payload.get("timestamp")),
            raw=payload,
        )

    async def submit_auth_2fa(
        self,
        *,
        platform: WappiPlatform,
        profile_id: str,
        pwd_code: str,
    ) -> WappiAuth2FAResult:
        path = _AUTH_2FA_PATHS.get(platform)
        if not path:
            raise WappiClientError("2FA auth is not supported for this platform")

        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise WappiClientError("profile_id is required")
        normalized_pwd_code = pwd_code.strip()
        if not normalized_pwd_code:
            raise WappiClientError("pwd_code is required")

        payload = await self._request_json(
            method="POST",
            path=path,
            params={"profile_id": normalized_profile_id},
            json={"pwd_code": normalized_pwd_code},
        )
        status = str(payload.get("status") or "done").strip()
        detail = str(payload.get("detail")).strip() if payload.get("detail") is not None else None
        if status and status.lower() not in {"done", "ok", "success"}:
            raise WappiClientError(detail or f"2FA auth request returned status '{status}'")

        return WappiAuth2FAResult(
            status=status or "done",
            detail=detail,
            uuid=str(payload.get("uuid")) if payload.get("uuid") is not None else None,
            time=str(payload.get("time")) if payload.get("time") is not None else None,
            timestamp=_to_int_or_none(payload.get("timestamp")),
            raw=payload,
        )

    async def send_telegram_sync_message(
        self,
        *,
        profile_id: str,
        body: str,
        recipient: str,
    ) -> WappiSyncMessageSendResult:
        """Отправка текста через Wappi Telegram (tapi) sync API."""
        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise WappiClientError("profile_id is required")
        text = (body or "").strip()
        if not text:
            raise WappiClientError("body is required")
        to_recipient = (recipient or "").strip()
        if not to_recipient:
            raise WappiClientError("recipient is required")

        payload = await self._request_json(
            method="POST",
            path=_TAPI_SYNC_MESSAGE_SEND_PATH,
            params={"profile_id": normalized_profile_id},
            json={"body": text, "recipient": to_recipient},
        )
        status = str(payload.get("status") or "done").strip()
        detail = str(payload.get("detail")).strip() if payload.get("detail") is not None else None
        if status and status.lower() not in {"done", "ok", "success"}:
            raise WappiClientError(detail or f"Send message returned status '{status}'")
        return WappiSyncMessageSendResult(status=status or "done", detail=detail, raw=payload)

    async def send_max_sync_message(
        self,
        *,
        profile_id: str,
        bot_id: str,
        body: str,
        recipient: str,
        chat_id: str,
        manager: dict[str, Any] | None = None,
    ) -> WappiSyncMessageSendResult:
        """Отправка текста через Wappi MAX API (maxapi/sync/message/send)."""
        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise WappiClientError("profile_id is required")
        normalized_bot_id = bot_id.strip()
        if not normalized_bot_id:
            raise WappiClientError("bot_id is required")
        text = (body or "").strip()
        if not text:
            raise WappiClientError("body is required")
        to_recipient = (recipient or "").strip()
        if not to_recipient:
            raise WappiClientError("recipient is required")
        to_chat = (chat_id or "").strip()
        if not to_chat:
            raise WappiClientError("chat_id is required")

        send_json: dict[str, Any] = {
            "recipient": to_recipient,
            "chat_id": to_chat,
            "body": text,
        }
        if manager:
            send_json["manager"] = manager

        payload = await self._request_json_or_text(
            method="POST",
            path=_MAXAPI_SYNC_MESSAGE_SEND_PATH,
            params={"profile_id": normalized_profile_id, "bot_id": normalized_bot_id},
            json=send_json,
            accept="text/plain, application/json",
        )
        status = str(payload.get("status") or "done").strip()
        detail = str(payload.get("detail")).strip() if payload.get("detail") is not None else None
        if status and status.lower() not in {"done", "ok", "success"}:
            raise WappiClientError(detail or f"Send message returned status '{status}'")
        return WappiSyncMessageSendResult(status=status or "done", detail=detail, raw=payload)

    async def send_telegram_async_message(
        self,
        *,
        profile_id: str,
        body: str,
        recipient: str,
        timeout_from: int | None = None,
        timeout_to: int | None = None,
    ) -> WappiAsyncMessageSendResult:
        """Отправка текста через Wappi Telegram (tapi) async API."""
        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise WappiClientError("profile_id is required")
        text = (body or "").strip()
        if not text:
            raise WappiClientError("body is required")
        to_recipient = (recipient or "").strip()
        if not to_recipient:
            raise WappiClientError("recipient is required")

        timeout_params = self._build_timeout_query_params(
            timeout_from=timeout_from,
            timeout_to=timeout_to,
        )
        payload = await self._request_json_or_text(
            method="POST",
            path=_TAPI_ASYNC_MESSAGE_SEND_PATH,
            params={"profile_id": normalized_profile_id, **timeout_params},
            json={"body": text, "recipient": to_recipient},
            accept="application/json, text/plain",
        )
        return self._build_async_send_result(payload, operation_name="Telegram async send")

    async def send_whatsapp_async_message(
        self,
        *,
        profile_id: str,
        body: str,
        recipient: str,
        timeout_from: int | None = None,
        timeout_to: int | None = None,
    ) -> WappiAsyncMessageSendResult:
        """Отправка текста через Wappi WhatsApp (/api/async/message/send)."""
        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise WappiClientError("profile_id is required")
        text = (body or "").strip()
        if not text:
            raise WappiClientError("body is required")
        to_recipient = (recipient or "").strip()
        if not to_recipient:
            raise WappiClientError("recipient is required")

        timeout_params = self._build_timeout_query_params(
            timeout_from=timeout_from,
            timeout_to=timeout_to,
        )
        payload = await self._request_json_or_text(
            method="POST",
            path=_API_ASYNC_MESSAGE_SEND_PATH,
            params={"profile_id": normalized_profile_id, **timeout_params},
            json={"body": text, "recipient": to_recipient},
            accept="application/json, text/plain",
        )
        return self._build_async_send_result(payload, operation_name="WhatsApp async send")

    async def send_max_async_message(
        self,
        *,
        profile_id: str,
        body: str,
        recipient: str | None = None,
        chat_id: str | None = None,
        bot_id: str | int | None = None,
        manager: dict[str, Any] | None = None,
        timeout_from: int | None = None,
        timeout_to: int | None = None,
    ) -> WappiAsyncMessageSendResult:
        """Отправка текста через Wappi MAX (/maxapi/async/message/send)."""
        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise WappiClientError("profile_id is required")
        text = (body or "").strip()
        if not text:
            raise WappiClientError("body is required")

        to_recipient = (recipient or "").strip() or None
        to_chat_id = (chat_id or "").strip() or None
        if not to_recipient and not to_chat_id:
            raise WappiClientError("recipient or chat_id is required")

        params: dict[str, Any] = {"profile_id": normalized_profile_id}
        timeout_params = self._build_timeout_query_params(
            timeout_from=timeout_from,
            timeout_to=timeout_to,
        )
        params.update(timeout_params)

        normalized_bot_id = str(bot_id).strip() if bot_id is not None else ""
        if normalized_bot_id:
            params["bot_id"] = normalized_bot_id

        send_json: dict[str, Any] = {"body": text}
        if to_recipient:
            send_json["recipient"] = to_recipient
        if to_chat_id:
            send_json["chat_id"] = to_chat_id
        if manager:
            if not isinstance(manager, dict):
                raise WappiClientError("manager must be a JSON object")
            send_json["manager"] = manager

        payload = await self._request_json_or_text(
            method="POST",
            path=_MAXAPI_ASYNC_MESSAGE_SEND_PATH,
            params=params,
            json=send_json,
            accept="application/json, text/plain",
        )
        return self._build_async_send_result(payload, operation_name="MAX async send")

    def _build_timeout_query_params(
        self,
        *,
        timeout_from: int | None,
        timeout_to: int | None,
    ) -> dict[str, int]:
        normalized_from = _normalize_timeout_param(timeout_from, field_name="timeout_from")
        normalized_to = _normalize_timeout_param(timeout_to, field_name="timeout_to")
        if normalized_from is None and normalized_to is None:
            return {}
        if normalized_from is None:
            normalized_from = normalized_to
        if normalized_to is None:
            normalized_to = normalized_from
        if normalized_from is None or normalized_to is None:
            return {}
        if normalized_from > normalized_to:
            raise WappiClientError("timeout_from must be less than or equal to timeout_to")
        return {
            "timeout_from": normalized_from,
            "timeout_to": normalized_to,
        }

    def _build_async_send_result(
        self,
        payload: dict[str, Any],
        *,
        operation_name: str,
    ) -> WappiAsyncMessageSendResult:
        status = str(payload.get("status")).strip() if payload.get("status") is not None else ""
        detail = str(payload.get("detail")).strip() if payload.get("detail") is not None else None
        if not status:
            raise WappiClientError(f"{operation_name} response is missing status")
        if status.lower() not in {"done", "ok", "success"}:
            raise WappiClientError(detail or f"{operation_name} returned status '{status}'")
        return WappiAsyncMessageSendResult(
            status=status,
            detail=detail,
            task_id=str(payload.get("task_id")).strip() if payload.get("task_id") is not None else None,
            time=str(payload.get("time")) if payload.get("time") is not None else None,
            timestamp=_to_int_or_none(payload.get("timestamp")),
            uuid=str(payload.get("uuid")).strip() if payload.get("uuid") is not None else None,
            command_start=str(payload.get("command_start")) if payload.get("command_start") is not None else None,
            command_end=str(payload.get("command_end")) if payload.get("command_end") is not None else None,
            raw=payload,
        )

    async def _request_json(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        accept: str | None = None,
    ) -> dict[str, Any]:
        response = await self._request_response(
            method=method,
            path=path,
            params=params,
            json=json,
            accept=accept,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise WappiClientError("Service returned invalid JSON response") from exc
        if not isinstance(payload, dict):
            raise WappiClientError("Service response must be a JSON object")
        return payload

    async def _request_json_or_text(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        accept: str | None = None,
    ) -> dict[str, Any]:
        response = await self._request_response(
            method=method,
            path=path,
            params=params,
            json=json,
            accept=accept,
        )
        text_body = response.text.strip()
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str):
            normalized_payload = payload.strip()
            return {"detail": normalized_payload} if normalized_payload else {}
        if payload is None:
            return {"detail": text_body} if text_body else {}
        raise WappiClientError("Service response must be a JSON object or plain text")

    async def _request_response(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        accept: str | None = None,
    ) -> httpx.Response:
        url = urljoin(f"{self._base_url}/", path.lstrip("/"))
        headers = {
            "Authorization": self._api_token,
            "Accept": accept or "application/json",
        }
        response: httpx.Response | None = None
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._retry_attempts + 1),
                wait=wait_exponential(min=self._retry_min_seconds, max=self._retry_max_seconds),
                retry=retry_if_exception(_is_retryable_exception),
                reraise=True,
            ):
                with attempt:
                    async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                        response = await client.request(
                            method,
                            url,
                            params=params or None,
                            json=json,
                            headers=headers,
                        )
                    response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            logger.warning(
                "wappi_http_status_error",
                path=path,
                status_code=exc.response.status_code,
                body=body,
            )
            raise WappiClientError(
                f"Request failed: {exc.response.status_code} {body}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("wappi_http_error", path=path, error=str(exc))
            raise WappiClientError("Request failed due to network error") from exc

        if response is None:
            raise WappiClientError("Request finished without response")
        return response
