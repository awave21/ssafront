"""Client for interacting with the SQNS CRM stack."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable
import asyncio
from urllib.parse import urljoin

import httpx
import structlog

from app.utils.phone import normalize_phone_number

logger = structlog.get_logger(__name__)


class SQNSClientError(Exception):
    """Raised when a SQNS interaction fails."""


DEFAULT_TOKEN_PATH = "/api/v2/auth/token"
DEFAULT_LOGIN_PATH = "/api/v2/auth"
TOKEN_EXPIRY_MARGIN = 30


def _build_host_url(host: str, path: str) -> str:
    host = host.rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = f"https://{host}"
    return urljoin(f"{host}/", path.lstrip("/"))


async def fetch_token_by_login(
    host: str,
    email: str,
    password: str,
    *,
    default_resource_id: int | None = None,
    login_path: str = DEFAULT_LOGIN_PATH,
    timeout_seconds: int = 15,
) -> str:
    """
    Получить Bearer-токен SQNS по email и паролю.
    POST {host}{login_path} с JSON {email, password, defaultResourceId?}.
    Ответ: массив [{ "status": "success", "token": "...", "user": {...} }] или объект с token.
    """
    url = _build_host_url(host, login_path)
    body: dict[str, Any] = {"email": email, "password": password}
    if default_resource_id is not None:
        body["defaultResourceId"] = default_resource_id
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            url,
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
    if response.status_code >= 400:
        raise SQNSClientError(f"login {response.status_code}: {response.text}")
    try:
        raw = response.json()
    except ValueError as exc:
        raise SQNSClientError("invalid login response") from exc
    # Ответ: массив [{ "status": "success", "token": "...", "user": {...} }] или объект
    payload = raw[0] if isinstance(raw, list) and raw else raw
    if not isinstance(payload, dict):
        raise SQNSClientError("login response missing token")
    token = payload.get("token") or payload.get("access_token") or payload.get("bearer")
    if not token and isinstance(payload.get("data"), dict):
        data = payload["data"]
        token = data.get("token") or data.get("access_token")
    if not token:
        raise SQNSClientError("login response missing token")
    return str(token)


class SQNSClient:
    def __init__(
        self,
        host: str,
        api_key: str,
        *,
        token_path: str | None = None,
        bearer_token: str | None = None,
        timeout_seconds: int = 15,
    ):
        self._host = host
        self._api_key = api_key
        self._token_path = token_path or DEFAULT_TOKEN_PATH
        self._bearer_token = bearer_token
        self._timeout_seconds = timeout_seconds
        self._token: str | None = None
        self._expires_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def _fetch_token(self) -> str:
        url = _build_host_url(self._host, self._token_path)
        headers = {"Accept": "application/json", "x-api-key": self._api_key}
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(url, headers=headers)
        if response.status_code >= 400:
            raise SQNSClientError(f"token error {response.status_code}: {response.text}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SQNSClientError("invalid token response") from exc
        token = payload.get("access_token") or payload.get("token") or payload.get("bearer")
        if not token:
            raise SQNSClientError("token response missing token")
        expires = payload.get("expires_in")
        if isinstance(expires, (int, float)):
            expires_delta = int(expires)
        elif isinstance(expires, str) and expires.isdigit():
            expires_delta = int(expires)
        else:
            expires_delta = None
        if expires_delta:
            self._expires_at = datetime.utcnow() + timedelta(seconds=expires_delta)
        else:
            self._expires_at = None
        self._token = token
        logger.debug("sqns_token_refreshed", host=self._host)
        return token

    async def _ensure_token(self) -> str:
        if self._bearer_token:
            return self._bearer_token
        async with self._lock:
            now = datetime.utcnow()
            if self._token and self._expires_at and now + timedelta(seconds=TOKEN_EXPIRY_MARGIN) < self._expires_at:
                return self._token
            if self._token and self._expires_at is None:
                return self._token
            return await self._fetch_token()

    def _invalidate_token(self) -> None:
        self._token = None
        self._expires_at = None

    @staticmethod
    def _to_positive_int(value: Any, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    @staticmethod
    def _to_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y"}:
                return True
            if normalized in {"0", "false", "no", "n"}:
                return False
        return default

    def _normalize_page_payload(
        self,
        response: Any,
        *,
        params: dict[str, Any],
        nested_keys: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        if isinstance(response, dict):
            data = response.get("data")
            if isinstance(data, list):
                meta = response.get("meta") or response.get("pagination")
                return {
                    "data": data,
                    "meta": meta if isinstance(meta, dict) else {},
                }

            for key in nested_keys:
                nested = response.get(key)
                if not isinstance(nested, dict):
                    continue
                nested_data = nested.get("data")
                if isinstance(nested_data, list):
                    nested_meta = nested.get("meta") or nested.get("pagination")
                    return {
                        "data": nested_data,
                        "meta": nested_meta if isinstance(nested_meta, dict) else {},
                    }
        elif isinstance(response, list):
            return {
                "data": response,
                "meta": {
                    "page": params.get("page", 1),
                    "lastPage": params.get("page", 1),
                    "maxPerPage": params.get("perPage") or params.get("pageSize"),
                    "total": len(response),
                },
            }

        raise SQNSClientError("response invalid format")

    @staticmethod
    def _parse_date_input(value: str) -> date:
        text = (value or "").strip()
        if not text:
            raise SQNSClientError("date range value is empty")

        if "T" in text:
            normalized = text.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized).date()
            except ValueError as exc:
                raise SQNSClientError(f"invalid datetime value: {value}") from exc

        try:
            return date.fromisoformat(text)
        except ValueError as exc:
            raise SQNSClientError(f"invalid date value: {value}") from exc

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> Any:
        url = _build_host_url(self._host, path)
        token = await self._ensure_token()
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.request(method, url, params=params or None, json=json, headers=headers)
        if response.status_code == 401:
            self._invalidate_token()
            token = await self._ensure_token()
            headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.request(
                    method,
                    url,
                    params=params or None,
                    json=json,
                    headers=headers,
                )
        if response.status_code >= 400:
            raise SQNSClientError(f"{path} {response.status_code}: {response.text}")
        if response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    async def list_resources(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/v2/resource")

    async def list_employees_page(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        modificate: int | None = None,
        is_fired: int = 0,
        is_deleted: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": max(page, 1),
            "perPage": max(per_page, 1),
            "isFired": is_fired,
            "isDeleted": is_deleted,
        }
        if modificate is not None:
            params["modificate"] = modificate

        response = await self._request("GET", "/api/v2/employee", params=params)
        try:
            return self._normalize_page_payload(response, params=params, nested_keys=("resources",))
        except SQNSClientError as exc:
            raise SQNSClientError("employee response invalid format") from exc

    async def list_all_employees(
        self,
        *,
        per_page: int = 100,
        modificate: int | None = None,
        is_fired: int = 0,
        is_deleted: int = 0,
    ) -> list[dict[str, Any]]:
        employees: list[dict[str, Any]] = []
        page = 1
        visited_pages: set[int] = set()

        while True:
            if page in visited_pages:
                logger.warning("sqns_employee_pagination_loop", host=self._host, page=page)
                break
            visited_pages.add(page)

            payload = await self.list_employees_page(
                page=page,
                per_page=per_page,
                modificate=modificate,
                is_fired=is_fired,
                is_deleted=is_deleted,
            )
            data = payload.get("data", [])
            meta = payload.get("meta", {})
            if isinstance(data, list):
                employees.extend(item for item in data if isinstance(item, dict))

            current_page = self._to_positive_int(meta.get("page"), page) if isinstance(meta, dict) else page
            last_page = (
                self._to_positive_int(meta.get("lastPage"), current_page)
                if isinstance(meta, dict)
                else current_page
            )
            if current_page >= last_page:
                break
            page = current_page + 1

        return employees

    async def list_clients_page(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        modificate: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": max(page, 1),
            "perPage": max(per_page, 1),
        }
        if modificate is not None:
            params["modificate"] = modificate

        response = await self._request("GET", "/api/v2/client", params=params)
        try:
            return self._normalize_page_payload(response, params=params)
        except SQNSClientError as exc:
            raise SQNSClientError("client response invalid format") from exc

    async def list_all_clients(
        self,
        *,
        per_page: int = 100,
        modificate: int | None = None,
    ) -> list[dict[str, Any]]:
        clients: list[dict[str, Any]] = []
        page = 1
        visited_pages: set[int] = set()

        while True:
            if page in visited_pages:
                logger.warning("sqns_client_pagination_loop", host=self._host, page=page)
                break
            visited_pages.add(page)

            payload = await self.list_clients_page(
                page=page,
                per_page=per_page,
                modificate=modificate,
            )
            data = payload.get("data", [])
            meta = payload.get("meta", {})
            if isinstance(data, list):
                clients.extend(item for item in data if isinstance(item, dict))

            current_page = self._to_positive_int(meta.get("page"), page) if isinstance(meta, dict) else page
            last_page = (
                self._to_positive_int(meta.get("lastPage"), current_page)
                if isinstance(meta, dict)
                else current_page
            )
            if current_page >= last_page:
                break
            page = current_page + 1

        return clients

    async def list_services_page(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        modificate: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": max(page, 1),
            "perPage": max(per_page, 1),
        }
        if modificate is not None:
            params["modificate"] = modificate
        response = await self._request("GET", "/api/v2/service", params=params)
        try:
            return self._normalize_page_payload(response, params=params)
        except SQNSClientError as exc:
            raise SQNSClientError("service response invalid format") from exc

    async def list_all_services(
        self,
        *,
        per_page: int = 100,
        modificate: int | None = None,
    ) -> list[dict[str, Any]]:
        services: list[dict[str, Any]] = []
        page = 1
        visited_pages: set[int] = set()

        while True:
            if page in visited_pages:
                logger.warning("sqns_service_pagination_loop", host=self._host, page=page)
                break
            visited_pages.add(page)

            payload = await self.list_services_page(page=page, per_page=per_page, modificate=modificate)
            data = payload.get("data", [])
            meta = payload.get("meta", {})
            if isinstance(data, list):
                services.extend(item for item in data if isinstance(item, dict))

            current_page = self._to_positive_int(meta.get("page"), page) if isinstance(meta, dict) else page
            last_page = (
                self._to_positive_int(meta.get("lastPage"), current_page)
                if isinstance(meta, dict)
                else current_page
            )
            if current_page >= last_page:
                break
            page = current_page + 1

        return services

    def _parse_booking_services_response_page(
        self,
        response: Any,
        *,
        page: int,
    ) -> tuple[list[dict[str, Any]], int | None]:
        """
        Ответ GET /api/v2/booking/service: в документации SQNS — {\"services\": [...]}.
        Некоторые инсталляции могут отдавать пагинацию как у /api/v2/service (data/meta).
        """
        if isinstance(response, list):
            return [x for x in response if isinstance(x, dict)], 1
        if not isinstance(response, dict):
            return [], 1
        services = response.get("services")
        if isinstance(services, list):
            return [x for x in services if isinstance(x, dict)], None
        try:
            payload = self._normalize_page_payload(
                response,
                params={"page": page, "perPage": 100},
            )
        except SQNSClientError:
            return [], None
        data = payload.get("data", [])
        meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
        items = [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []
        last_page = self._to_positive_int(meta.get("lastPage"), page) if meta else page
        return items, last_page

    async def list_all_booking_services(
        self,
        *,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Услуги для онлайн-записи (док.: раздел «Онлайн запись») — содержат привязку resources[] к ресурсам записи.
        Выгрузка GET /api/v2/service этого поля не содержит.
        """
        collected: list[dict[str, Any]] = []
        page = 1
        visited: set[int] = set()
        while True:
            if page in visited:
                break
            visited.add(page)
            params: dict[str, Any] = {"page": max(page, 1), "perPage": max(per_page, 1)}
            response = await self._request("GET", "/api/v2/booking/service", params=params)
            items, last_page = self._parse_booking_services_response_page(response, page=page)
            collected.extend(items)
            if last_page is None:
                break
            if page >= last_page or not items:
                break
            page += 1
            if page > 500:
                logger.warning("sqns_booking_services_page_limit", host=self._host)
                break
        return collected

    async def get_booking_service_detail(self, service_external_id: int) -> dict[str, Any] | None:
        """Док.: GET /api/v2/booking/service/{id} → {\"service\": {...}} с resources."""
        sid = int(service_external_id)
        try:
            response = await self._request("GET", f"/api/v2/booking/service/{sid}")
        except SQNSClientError as exc:
            logger.warning("sqns_get_booking_service_detail_failed", service_id=sid, error=str(exc))
            return None
        if isinstance(response, dict):
            inner = response.get("service")
            if isinstance(inner, dict):
                return inner
        return None

    async def list_services(self) -> list[dict[str, Any]]:
        try:
            return await self.list_all_services(per_page=100)
        except SQNSClientError as exc:
            logger.warning(
                "sqns_service_v2_fallback",
                host=self._host,
                error=str(exc),
            )
            legacy_response = await self._request("GET", "/api/v2/booking/service")
            if isinstance(legacy_response, list):
                return [item for item in legacy_response if isinstance(item, dict)]
            if isinstance(legacy_response, dict):
                services_data = legacy_response.get("services")
                if isinstance(services_data, list):
                    return [item for item in services_data if isinstance(item, dict)]
            raise SQNSClientError("service response invalid format")

    async def list_commodities_page(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        modificate: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": max(page, 1),
            "perPage": max(per_page, 1),
        }
        if modificate is not None:
            params["modificate"] = modificate
        response = await self._request("GET", "/api/v2/commodity", params=params)
        try:
            return self._normalize_page_payload(response, params=params)
        except SQNSClientError as exc:
            raise SQNSClientError("commodity response invalid format") from exc

    async def list_all_commodities(
        self,
        *,
        per_page: int = 100,
        modificate: int | None = None,
    ) -> list[dict[str, Any]]:
        commodities: list[dict[str, Any]] = []
        page = 1
        visited_pages: set[int] = set()

        while True:
            if page in visited_pages:
                logger.warning("sqns_commodity_pagination_loop", host=self._host, page=page)
                break
            visited_pages.add(page)

            payload = await self.list_commodities_page(page=page, per_page=per_page, modificate=modificate)
            data = payload.get("data", [])
            meta = payload.get("meta", {})
            if isinstance(data, list):
                commodities.extend(item for item in data if isinstance(item, dict))

            current_page = self._to_positive_int(meta.get("page"), page) if isinstance(meta, dict) else page
            last_page = (
                self._to_positive_int(meta.get("lastPage"), current_page)
                if isinstance(meta, dict)
                else current_page
            )
            if current_page >= last_page:
                break
            page = current_page + 1

        return commodities

    async def list_slots(
        self,
        resource_id: int,
        date: str,
        *,
        service_ids: Iterable[int] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"date": date}
        if service_ids:
            params["serviceIds[]"] = list(service_ids)
        return await self._request("GET", f"/api/v2/resource/{resource_id}/time", params=params)

    async def list_visits_page(
        self,
        date_from: str,
        date_till: str,
        *,
        page: int = 1,
        per_page: int = 100,
        modificate: int | None = None,
    ) -> dict[str, Any]:
        normalized_per_page = max(min(per_page, 100), 1)
        params: dict[str, Any] = {
            "dateFrom": date_from,
            "dateTill": date_till,
            # В разных инсталляциях SQNS встречаются оба названия параметра.
            "peerPage": normalized_per_page,
            "perPage": normalized_per_page,
            "page": max(page, 1),
        }
        if modificate is not None:
            params["modificate"] = modificate
        response = await self._request("GET", "/api/v2/visit", params=params)
        try:
            return self._normalize_page_payload(response, params=params)
        except SQNSClientError as exc:
            raise SQNSClientError("visit response invalid format") from exc

    async def list_all_visits(
        self,
        date_from: str,
        date_till: str,
        *,
        per_page: int = 100,
        modificate: int | None = None,
    ) -> list[dict[str, Any]]:
        visits: list[dict[str, Any]] = []
        page = 1
        visited_pages: set[int] = set()

        while True:
            if page in visited_pages:
                logger.warning("sqns_visit_pagination_loop", host=self._host, page=page)
                break
            visited_pages.add(page)

            payload = await self.list_visits_page(
                date_from,
                date_till,
                page=page,
                per_page=per_page,
                modificate=modificate,
            )
            data = payload.get("data", [])
            meta = payload.get("meta", {})
            if isinstance(data, list):
                visits.extend(item for item in data if isinstance(item, dict))

            current_page = self._to_positive_int(meta.get("page"), page) if isinstance(meta, dict) else page
            last_page = (
                self._to_positive_int(meta.get("lastPage"), current_page)
                if isinstance(meta, dict)
                else current_page
            )
            if current_page >= last_page:
                break
            page = current_page + 1

        return visits

    async def list_visits(
        self,
        date_from: str,
        date_till: str,
        *,
        peer_page: int = 100,
        page: int | None = None,
        modificate: int | None = None,
    ) -> dict[str, Any]:
        return await self.list_visits_page(
            date_from,
            date_till,
            page=page or 1,
            per_page=peer_page,
            modificate=modificate,
        )

    async def list_payments_page(
        self,
        date_from: str,
        date_to: str,
        *,
        page: int = 1,
        page_size: int = 100,
        client_id: int | None = None,
        payment_method: str | None = None,
        payment_type: str | None = None,
    ) -> dict[str, Any]:
        parsed_date_from = self._parse_date_input(date_from)
        parsed_date_to = self._parse_date_input(date_to)
        if parsed_date_to < parsed_date_from:
            raise SQNSClientError("dateTo must be greater than or equal to dateFrom")
        if (parsed_date_to - parsed_date_from).days > 90:
            raise SQNSClientError("payments date range must not exceed 90 days")

        params: dict[str, Any] = {
            "dateFrom": date_from,
            "dateTo": date_to,
            "page": max(page, 1),
            "pageSize": max(min(page_size, 100), 1),
        }
        if client_id is not None:
            params["clientId"] = client_id
        if payment_method:
            params["paymentMethod"] = payment_method
        if payment_type:
            params["paymentType"] = payment_type

        response = await self._request("GET", "/api/v2/payments", params=params)
        try:
            return self._normalize_page_payload(response, params=params)
        except SQNSClientError as exc:
            raise SQNSClientError("payments response invalid format") from exc

    async def list_all_payments(
        self,
        date_from: str,
        date_to: str,
        *,
        page_size: int = 100,
        client_id: int | None = None,
        payment_method: str | None = None,
        payment_type: str | None = None,
    ) -> list[dict[str, Any]]:
        payments: list[dict[str, Any]] = []
        page = 1
        visited_pages: set[int] = set()

        while True:
            if page in visited_pages:
                logger.warning("sqns_payments_pagination_loop", host=self._host, page=page)
                break
            visited_pages.add(page)

            payload = await self.list_payments_page(
                date_from,
                date_to,
                page=page,
                page_size=page_size,
                client_id=client_id,
                payment_method=payment_method,
                payment_type=payment_type,
            )
            data = payload.get("data", [])
            meta = payload.get("meta", {})
            if isinstance(data, list):
                payments.extend(item for item in data if isinstance(item, dict))

            if not isinstance(meta, dict):
                break

            current_page = self._to_positive_int(meta.get("page"), page)
            has_more = self._to_bool(meta.get("hasMore"), default=False)
            if has_more:
                page = current_page + 1
                continue

            last_page = self._to_positive_int(meta.get("lastPage"), current_page)
            if current_page >= last_page:
                break
            page = current_page + 1

        return payments

    async def find_client_by_phone(self, phone: str) -> dict[str, Any]:
        normalized = normalize_phone_number(phone)
        return await self._request("GET", f"/api/v2/client/phone/{normalized}")

    async def create_visit(self, visit_payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/v2/visit", json={"visit": visit_payload})

    async def update_visit(self, visit_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"/api/v2/visit/{visit_id}", json=payload)

    async def delete_visit(self, visit_id: int) -> None:
        await self._request("DELETE", f"/api/v2/visit/{visit_id}")
