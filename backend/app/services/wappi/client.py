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
class WappiProfileDeleteResult:
    status: str
    detail: str | None = None
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
    uuid: str | None = None
    time: str | None = None
    timestamp: int | None = None
    raw: dict[str, Any] | None = None


_CREATE_PROFILE_PATHS: dict[WappiPlatform, str] = {
    WappiPlatform.WHATSAPP: "/api/profile/add",
    WappiPlatform.TELEGRAM_PHONE: "/tapi/profile/add",
    WappiPlatform.MAX: "/maxapi/profile/add",
}

_DELETE_PROFILE_PATHS: dict[WappiPlatform, str] = {
    WappiPlatform.WHATSAPP: "/api/profile/delete",
    WappiPlatform.TELEGRAM_PHONE: "/tapi/profile/delete",
    WappiPlatform.MAX: "/maxapi/profile/delete",
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
_BALANCE_ADD_DAYS_PATH = "/payments/balance/add_days"
_AVAILABLE_TARIFF_IDS = {1, 2, 3, 4}


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

        normalized_profile_ids: list[str] = []
        for value in profile_ids or []:
            normalized = str(value).strip()
            if normalized:
                normalized_profile_ids.append(normalized)
        if not normalized_profile_ids:
            normalized_profile_ids = [normalized_profile_uuid]
        elif normalized_profile_uuid not in normalized_profile_ids:
            normalized_profile_ids.insert(0, normalized_profile_uuid)

        payload = {
            "profile_uuid": normalized_profile_uuid,
            "tariff_id": tariff_id,
            "profile_ids": normalized_profile_ids,
        }
        normalized_code = (code or "").strip()
        if normalized_code:
            payload["code"] = normalized_code

        response_payload = await self._request_json(
            method="POST",
            path=_BALANCE_ADD_DAYS_PATH,
            json=payload,
        )
        return WappiBalanceAddDaysResult(
            status=str(response_payload.get("status") or "done"),
            detail=str(response_payload.get("detail")) if response_payload.get("detail") is not None else None,
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
        qr_raw = payload.get("qrCode") or payload.get("qr_code") or payload.get("detail")
        qr_code = _normalize_qr_code(str(qr_raw or ""))
        if not qr_code:
            raise WappiClientError("QR code is missing in service response")

        return WappiAuthQrResult(
            status=str(payload.get("status") or "done"),
            qr_code=qr_code,
            uuid=str(payload.get("uuid")) if payload.get("uuid") is not None else None,
            time=str(payload.get("time")) if payload.get("time") is not None else None,
            timestamp=_to_int_or_none(payload.get("timestamp")),
            raw=payload,
        )

    async def _request_json(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = urljoin(f"{self._base_url}/", path.lstrip("/"))
        headers = {
            "Authorization": self._api_token,
            "Accept": "application/json",
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

        try:
            payload = response.json()
        except ValueError as exc:
            raise WappiClientError("Service returned invalid JSON response") from exc
        if not isinstance(payload, dict):
            raise WappiClientError("Service response must be a JSON object")
        return payload
