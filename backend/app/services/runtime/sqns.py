from __future__ import annotations

from datetime import date as date_cls
from typing import Any
import re

import structlog
from pydantic_ai.tools import Tool as PydanticTool
from sqlalchemy import select

from app.db.models.agent import Agent
from app.db.models.sqns_service import SqnsResource
from app.schemas.auth import AuthContext
from app.services.runtime.utils import _safe_identifier
from app.services.sqns import SQNSClientError
from app.services.tool_executor import ToolExecutionError

logger = structlog.get_logger("app.services.runtime")
_MAX_VISIT_PAGES = 200


def _sqns_error_payload(
    *,
    message: str,
    status_code: int | None,
    retryable: bool,
    user_message: str = "Произошла ошибка при обращении к SQNS.",
) -> dict[str, Any]:
    return {
        "ok": False,
        "retryable": retryable,
        "message": user_message,
        "error": {
            "message": message,
            "status_code": status_code,
        },
    }


def _parse_sqns_status_code(message: str) -> int | None:
    m = re.search(r"\s(?P<status>\d{3}):", message or "")
    if not m:
        return None
    try:
        return int(m.group("status"))
    except Exception:
        return None


def _build_visits_message(count: int) -> str:
    if count <= 0:
        return "Записи не найдены по указанному телефону и дате."
    return f"Найдено записей: {count}."


def _strip_client_visit_field(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload

    sanitized = dict(payload)
    sanitized.pop("visit", None)

    client_data = sanitized.get("client")
    if isinstance(client_data, dict):
        client_sanitized = dict(client_data)
        client_sanitized.pop("visit", None)
        sanitized["client"] = client_sanitized

    return sanitized


def _read_nested_value(payload: dict[str, Any], paths: tuple[tuple[str, ...], ...]) -> Any:
    for path in paths:
        current: Any = payload
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if current not in (None, ""):
                return current
    return None


def _extract_phone_from_visit(visit: Any) -> str | None:
    from app.utils.phone import normalize_phone_number

    if not isinstance(visit, dict):
        return None
    for path in (
        ("user", "phone"),
        ("client", "phone"),
        ("clientData", "phone"),
        ("visit", "user", "phone"),
        ("visit", "client", "phone"),
        ("visit", "clientData", "phone"),
    ):
        current: Any = visit
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if current in (None, ""):
                continue
            try:
                return normalize_phone_number(str(current))
            except Exception:
                return str(current)
    return None


def _extract_raw_visits(visits_payload: Any) -> list[Any]:
    if isinstance(visits_payload, list):
        return visits_payload
    if isinstance(visits_payload, dict):
        raw_visits = (
            visits_payload.get("data")
            or visits_payload.get("result")
            or visits_payload.get("visits")
            or visits_payload.get("items")
            or []
        )
        if isinstance(raw_visits, list):
            return raw_visits
    return []


def _set_filtered_visits(payload: dict[str, Any], filtered_visits: list[dict[str, Any]]) -> dict[str, Any]:
    safe_payload = dict(payload)
    if "data" in safe_payload:
        safe_payload["data"] = filtered_visits
    elif "result" in safe_payload:
        safe_payload["result"] = filtered_visits
    elif "visits" in safe_payload:
        safe_payload["visits"] = filtered_visits
    elif "items" in safe_payload:
        safe_payload["items"] = filtered_visits
    else:
        safe_payload["result"] = filtered_visits
    return safe_payload


def _filter_visits_by_phone(raw_visits: list[Any], normalized_phone: str) -> list[dict[str, Any]]:
    filtered_visits: list[dict[str, Any]] = []
    for visit in raw_visits:
        if _extract_phone_from_visit(visit) == normalized_phone and isinstance(visit, dict):
            filtered_visits.append(visit)
    return filtered_visits


def _normalize_date(date_value: str, field_name: str) -> str:
    value = (date_value or "").strip()
    if not value:
        raise ValueError(f"{field_name} обязателен.")
    try:
        return date_cls.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} должен быть в формате YYYY-MM-DD.") from exc


def _resolve_visits_period(
    *,
    date: str | None,
    date_from: str | None,
    date_till: str | None,
) -> tuple[str, str, dict[str, str]]:
    single_date = (date or "").strip() or None
    period_start = (date_from or "").strip() or None
    period_end = (date_till or "").strip() or None

    if single_date and (period_start or period_end):
        raise ValueError("Передай либо date, либо date_from и date_till, но не одновременно.")

    if single_date:
        normalized_single = _normalize_date(single_date, "date")
        return normalized_single, normalized_single, {"mode": "single", "date": normalized_single}

    if period_start or period_end:
        if not period_start or not period_end:
            raise ValueError("Для диапазона нужно передать оба поля: date_from и date_till.")
        normalized_from = _normalize_date(period_start, "date_from")
        normalized_till = _normalize_date(period_end, "date_till")
        if normalized_from > normalized_till:
            raise ValueError("date_from не может быть позже date_till.")
        return normalized_from, normalized_till, {
            "mode": "range",
            "date_from": normalized_from,
            "date_till": normalized_till,
        }

    raise ValueError("Укажи либо date, либо пару date_from и date_till.")


def _normalize_per_page(per_page: int) -> int:
    if per_page < 1 or per_page > 100:
        raise ValueError("per_page должен быть в диапазоне от 1 до 100.")
    return per_page


def _to_positive_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        if value.is_integer() and value > 0:
            return int(value)
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = int(text)
    except ValueError:
        return None
    return number if number > 0 else None


def _extract_meta_page(payload: Any, fallback: int) -> int:
    if not isinstance(payload, dict):
        return fallback
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return fallback
    return (
        _to_positive_int(meta.get("page"))
        or _to_positive_int(meta.get("currentPage"))
        or _to_positive_int(meta.get("current_page"))
        or fallback
    )


def _extract_meta_last_page(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return None
    return (
        _to_positive_int(meta.get("lastPage"))
        or _to_positive_int(meta.get("last_page"))
        or _to_positive_int(meta.get("totalPages"))
        or _to_positive_int(meta.get("total_pages"))
        or _to_positive_int(meta.get("pages"))
    )


async def _collect_visits_pages(
    client: Any,
    *,
    date_from: str,
    date_till: str,
    per_page: int,
    max_pages: int = _MAX_VISIT_PAGES,
) -> tuple[list[Any], Any, dict[str, int | None]]:
    raw_visits: list[Any] = []
    page = 1
    requested_pages: set[int] = set()
    first_payload: Any = {"result": []}
    last_page: int | None = None

    while True:
        if page in requested_pages:
            logger.warning("sqns_visit_pagination_loop_detected", page=page)
            break
        requested_pages.add(page)

        payload = await client.list_visits(
            date_from=date_from,
            date_till=date_till,
            peer_page=per_page,
            page=page,
        )
        if len(requested_pages) == 1:
            first_payload = payload

        raw_visits.extend(_extract_raw_visits(payload))

        current_page = _extract_meta_page(payload, fallback=page)
        page_last = _extract_meta_last_page(payload)
        if page_last is not None:
            last_page = page_last

        if page_last is None:
            break
        if current_page >= page_last:
            break
        if len(requested_pages) >= max_pages:
            logger.warning(
                "sqns_visit_pagination_limit_reached",
                max_pages=max_pages,
                current_page=current_page,
                last_page=page_last,
            )
            break

        page = current_page + 1

    return raw_visits, first_payload, {"pages_scanned": len(requested_pages), "last_page": last_page}


def _to_resource_key(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return None
    key = str(value).strip()
    return key or None


def _extract_resource_id(visit: dict[str, Any]) -> str | None:
    candidate = _read_nested_value(
        visit,
        (
            ("resourceId",),
            ("resource_id",),
            ("resource", "id"),
            ("resource", "resourceId"),
            ("visit", "resourceId"),
            ("visit", "resource_id"),
            ("visit", "resource", "id"),
            ("appointment", "resourceId"),
            ("appointment", "resource_id"),
        ),
    )
    return _to_resource_key(candidate)


def _extract_resource_name_map(resources_payload: Any) -> dict[str, str]:
    if isinstance(resources_payload, list):
        raw_resources = resources_payload
    elif isinstance(resources_payload, dict):
        raw_resources = (
            resources_payload.get("data")
            or resources_payload.get("resources")
            or resources_payload.get("result")
            or resources_payload.get("items")
            or []
        )
    else:
        raw_resources = []

    result: dict[str, str] = {}
    for item in raw_resources:
        if not isinstance(item, dict):
            continue
        resource_id = _to_resource_key(
            _read_nested_value(
                item,
                (
                    ("id",),
                    ("resourceId",),
                    ("resource_id",),
                    ("externalId",),
                    ("external_id",),
                ),
            )
        )
        resource_name = _read_nested_value(
            item,
            (
                ("name",),
                ("fullName",),
                ("full_name",),
                ("fio",),
                ("title",),
            ),
        )
        if resource_id and isinstance(resource_name, str) and resource_name.strip():
            result[resource_id] = resource_name.strip()
    return result


def _extract_service_name(visit: dict[str, Any]) -> str | None:
    direct_service_name = _read_nested_value(
        visit,
        (
            ("service", "name"),
            ("service_name",),
            ("serviceName",),
            ("visit", "service", "name"),
            ("appointment", "service", "name"),
        ),
    )
    if isinstance(direct_service_name, str) and direct_service_name.strip():
        return direct_service_name.strip()

    services = _read_nested_value(
        visit,
        (
            ("services",),
            ("visit", "services"),
            ("appointment", "services"),
            ("visit", "appointment", "services"),
        ),
    )
    if not isinstance(services, list):
        return None
    names = [
        str(item.get("name")).strip()
        for item in services
        if isinstance(item, dict) and item.get("name")
    ]
    if not names:
        return None
    if len(names) == 1:
        return names[0]
    return f"{names[0]} (+{len(names) - 1})"


def _extract_resource_name(visit: dict[str, Any], resource_name_by_id: dict[str, str] | None) -> str | None:
    direct_resource_name = _read_nested_value(
        visit,
        (
            ("resource", "name"),
            ("resource_name",),
            ("resourceName",),
            ("resourceData", "name"),
            ("visit", "resource", "name"),
            ("visit", "resourceData", "name"),
            ("appointment", "resource", "name"),
        ),
    )
    if isinstance(direct_resource_name, str) and direct_resource_name.strip():
        return direct_resource_name.strip()
    if not resource_name_by_id:
        return None
    resource_key = _extract_resource_id(visit)
    if not resource_key:
        return None
    return resource_name_by_id.get(resource_key)


def _compact_visit(visit: dict[str, Any], resource_name_by_id: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "visit_id": _read_nested_value(
            visit,
            (
                ("id",),
                ("visit_id",),
                ("visitId",),
                ("visit", "id"),
                ("visit", "visit_id"),
                ("visit", "visitId"),
            ),
        ),
        "datetime": _read_nested_value(
            visit,
            (
                ("datetime",),
                ("dateTime",),
                ("visit", "datetime"),
                ("visit", "dateTime"),
                ("appointment", "datetime"),
                ("visit", "appointment", "datetime"),
            ),
        ),
        "status": _read_nested_value(
            visit,
            (
                ("status",),
                ("visit", "status"),
            ),
        ),
        "service_name": _extract_service_name(visit),
        "resource_name": _extract_resource_name(visit, resource_name_by_id),
        "comment": _read_nested_value(
            visit,
            (
                ("comment",),
                ("visit", "comment"),
            ),
        ),
    }


try:
    from pydantic_ai.toolsets.fastmcp import FastMCPToolset
    from app.services.sqns.mcp_server import create_sqns_mcp_server

    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    logger.warning("fastmcp_not_available", message="FastMCP not installed, SQNS tools will use legacy approach")


async def _build_sqns_toolset(
    agent: Agent,
    user: AuthContext,
) -> FastMCPToolset:
    """
    Создать SQNS toolset используя FastMCP (если доступен) или legacy подход.

    Args:
        agent: Модель агента с SQNS конфигурацией
        user: Контекст аутентификации пользователя

    Returns:
        FastMCPToolset если fastmcp установлен
    """
    # Ленивая загрузка, чтобы избежать циклических импортов.
    from app.db.session import async_session_factory
    from app.services.sqns.client_factory import build_sqns_client_for_agent

    async with async_session_factory() as db:
        stmt = select(Agent).where(Agent.id == agent.id)
        fresh_agent = (await db.execute(stmt)).scalar_one_or_none()
        if not fresh_agent:
            raise ToolExecutionError("Agent not found")

        sqns_client = await build_sqns_client_for_agent(
            db,
            fresh_agent,
            tenant_id=fresh_agent.tenant_id,
        )

        if FASTMCP_AVAILABLE:
            logger.info(
                "using_fastmcp_for_sqns",
                agent_id=str(agent.id),
                approach="mcp_server",
            )
            mcp_server = create_sqns_mcp_server(
                sqns_client,
                db,
                fresh_agent.tenant_id,
                fresh_agent.id,
            )
            return FastMCPToolset(mcp_server)

    raise ToolExecutionError("FastMCP not available")


def build_sqns_legacy_tools(agent: Agent, user: AuthContext) -> list[PydanticTool]:
    from app.schemas.agent import get_sqns_tools_definitions

    sqns_tools_definitions = get_sqns_tools_definitions()
    available_names = {str(item.get("name")) for item in sqns_tools_definitions if isinstance(item, dict)}
    disabled_tools = {
        str(item).strip()
        for item in (agent.sqns_disabled_tools or [])
        if str(item).strip() and str(item).strip() in available_names
    }
    if disabled_tools:
        sqns_tools_definitions = [
            item for item in sqns_tools_definitions if str(item.get("name")) not in disabled_tools
        ]
    description_overrides = {
        str(key).strip(): str(value).strip()
        for key, value in (agent.sqns_tool_descriptions or {}).items()
        if str(key).strip() in available_names and str(value).strip()
    }
    if description_overrides:
        sqns_tools_definitions = [
            {
                **item,
                "description": description_overrides.get(str(item.get("name")), item.get("description", "")),
            }
            for item in sqns_tools_definitions
        ]
    logger.info(
        "sqns_tools_loading_legacy",
        agent_id=str(agent.id),
        tools_count=len(sqns_tools_definitions),
        tool_names=[d["name"] for d in sqns_tools_definitions],
    )

    tools: list[PydanticTool] = []
    for defn in sqns_tools_definitions:
        def make_sqns_tool(method_name: str, tool_name: str, description: str, schema: dict):
            async def _sqns_impl(**kwargs: Any) -> Any:
                from app.db.session import async_session_factory
                from app.services.sqns.client_factory import build_sqns_client_for_agent

                async with async_session_factory() as db:
                    stmt = select(Agent).where(Agent.id == agent.id)
                    agent_obj = (await db.execute(stmt)).scalar_one_or_none()
                    if not agent_obj:
                        raise ToolExecutionError("Agent not found")

                    client = await build_sqns_client_for_agent(
                        db,
                        agent_obj,
                        tenant_id=agent_obj.tenant_id,
                    )
                    method = getattr(client, method_name, None)
                    if not method:
                        raise ToolExecutionError(f"SQNS client missing method {method_name}")

                    try:
                        if method_name == "list_resources":
                            stmt = (
                                select(SqnsResource)
                                .where(
                                    SqnsResource.agent_id == agent_obj.id,
                                    SqnsResource.is_active == True,
                                    SqnsResource.active == True,
                                )
                                .order_by(SqnsResource.name)
                            )
                            resources = (await db.execute(stmt)).scalars().all()
                            return [
                                {
                                    "id": resource.external_id,
                                    "resource_id": resource.external_id,
                                    "name": resource.name,
                                    "specialization": resource.specialization,
                                    "information": resource.information,
                                    "isActive": resource.is_active,
                                    "active": resource.active,
                                }
                                for resource in resources
                            ]

                        if method_name == "create_visit":
                            from app.utils.phone import normalize_phone_number

                            _status_re = re.compile(r"\s(?P<status>\d{3}):")
                            user_name = (kwargs.get("user_name") or "").strip()
                            if not user_name:
                                raise ToolExecutionError(
                                    "user_name обязателен. Получи из sqns_find_client (client.name) или от пользователя."
                                )
                            phone_raw = (kwargs.get("phone") or "").strip()
                            if not phone_raw:
                                raise ToolExecutionError(
                                    "phone обязателен. Получи из sqns_find_client (client.phone) или от пользователя."
                                )
                            user_obj: dict[str, Any] = {
                                "name": user_name,
                                "phone": normalize_phone_number(phone_raw),
                            }
                            if kwargs.get("email") and (e := str(kwargs["email"]).strip()):
                                user_obj["email"] = e
                            visit_payload: dict[str, Any] = {
                                "user": user_obj,
                                "appointment": {
                                    "serviceIds": [str(kwargs["service_id"])],
                                    "resourceId": str(kwargs["resource_id"]),
                                    "datetime": kwargs["datetime"],
                                },
                            }
                            if kwargs.get("comment") and (c := str(kwargs["comment"]).strip()):
                                visit_payload["comment"] = c
                            try:
                                return await method(visit_payload)
                            except SQNSClientError as exc:
                                msg = str(exc)
                                m = _status_re.search(msg)
                                status = int(m.group("status")) if m else None
                                if status is not None and 400 <= status < 500:
                                    return {
                                        "ok": False,
                                        "retryable": False,
                                        "error": {
                                            "message": msg,
                                            "status_code": status,
                                        },
                                    }
                                raise

                        elif method_name == "update_visit":
                            _status_re = re.compile(r"\s(?P<status>\d{3}):")
                            visit_id = kwargs.pop("visit_id")
                            payload = {}
                            if "datetime" in kwargs:
                                payload["datetime"] = kwargs["datetime"]
                            if "comment" in kwargs:
                                payload["comment"] = kwargs["comment"]
                            if "status" in kwargs:
                                payload["status"] = kwargs["status"]
                            try:
                                return await method(visit_id, payload)
                            except SQNSClientError as exc:
                                msg = str(exc)
                                m = _status_re.search(msg)
                                status = int(m.group("status")) if m else None
                                if status is not None and 400 <= status < 500:
                                    return {
                                        "ok": False,
                                        "retryable": False,
                                        "error": {
                                            "message": msg,
                                            "status_code": status,
                                        },
                                    }
                                raise

                        elif method_name == "delete_visit":
                            _status_re = re.compile(r"\s(?P<status>\d{3}):")
                            visit_id = kwargs.get("visit_id")
                            try:
                                await method(visit_id)
                                return {"ok": True}
                            except SQNSClientError as exc:
                                msg = str(exc)
                                m = _status_re.search(msg)
                                status = int(m.group("status")) if m else None
                                if status is not None and 400 <= status < 500:
                                    return {
                                        "ok": False,
                                        "retryable": False,
                                        "error": {
                                            "message": msg,
                                            "status_code": status,
                                        },
                                    }
                                raise

                        elif method_name == "list_visits":
                            from app.utils.phone import normalize_phone_number

                            phone = str(kwargs.get("phone") or "").strip()
                            if not phone:
                                return _sqns_error_payload(
                                    message="phone обязателен для sqns_list_visits (фильтрация по клиенту).",
                                    status_code=422,
                                    retryable=False,
                                    user_message="Произошла ошибка при поиске записей клиента.",
                                )
                            try:
                                normalized_phone = normalize_phone_number(phone)
                                if tool_name == "sqns_client_visits":
                                    normalized_date_from, normalized_date_till, date_filter = _resolve_visits_period(
                                        date=str(kwargs.get("date") or "").strip() or None,
                                        date_from=str(kwargs.get("date_from") or "").strip() or None,
                                        date_till=str(kwargs.get("date_till") or "").strip() or None,
                                    )
                                else:
                                    normalized_date_from = _normalize_date(
                                        str(kwargs.get("date_from") or ""),
                                        "date_from",
                                    )
                                    normalized_date_till = _normalize_date(
                                        str(kwargs.get("date_till") or ""),
                                        "date_till",
                                    )
                                    if normalized_date_from > normalized_date_till:
                                        raise ValueError("date_from не может быть позже date_till.")
                                    date_filter = {
                                        "mode": "range",
                                        "date_from": normalized_date_from,
                                        "date_till": normalized_date_till,
                                    }
                                safe_per_page = _normalize_per_page(int(kwargs.get("per_page") or 100))

                                client_payload = _strip_client_visit_field(
                                    await client.find_client_by_phone(normalized_phone)
                                )
                                raw_visits, visits_payload, pagination = await _collect_visits_pages(
                                    client,
                                    date_from=normalized_date_from,
                                    date_till=normalized_date_till,
                                    per_page=safe_per_page,
                                )
                                filtered_visits = _filter_visits_by_phone(raw_visits, normalized_phone)

                                logger.info(
                                    "sqns_list_visits_filtered",
                                    tool_name=tool_name,
                                    phone=normalized_phone,
                                    date_from=normalized_date_from,
                                    date_till=normalized_date_till,
                                    raw_count=len(raw_visits),
                                    filtered_count=len(filtered_visits),
                                    pages_scanned=pagination.get("pages_scanned"),
                                    last_page=pagination.get("last_page"),
                                )

                                if tool_name == "sqns_client_visits":
                                    resource_name_by_id: dict[str, str] = {}
                                    try:
                                        resources_payload = await client.list_resources()
                                        resource_name_by_id = _extract_resource_name_map(resources_payload)
                                    except Exception as exc:
                                        # Best effort: если список специалистов недоступен, вернем compact без resource_name.
                                        logger.warning("sqns_client_visits_resource_map_error", error=str(exc))
                                    compact_visits = [_compact_visit(visit, resource_name_by_id) for visit in filtered_visits]
                                    return {
                                        "phone": normalized_phone,
                                        "date_filter": date_filter,
                                        "count": len(compact_visits),
                                        "visits": compact_visits,
                                        "message": _build_visits_message(len(compact_visits)),
                                    }

                                if isinstance(visits_payload, dict):
                                    safe_payload = _set_filtered_visits(visits_payload, filtered_visits)
                                    safe_payload["client"] = (
                                        client_payload.get("client") if isinstance(client_payload, dict) else client_payload
                                    )
                                    safe_payload["filtered_by_phone"] = normalized_phone
                                    safe_payload["message"] = _build_visits_message(len(filtered_visits))
                                    return safe_payload
                                return {
                                    "result": filtered_visits,
                                    "client": client_payload.get("client") if isinstance(client_payload, dict) else client_payload,
                                    "filtered_by_phone": normalized_phone,
                                    "message": _build_visits_message(len(filtered_visits)),
                                }
                            except ValueError as exc:
                                return _sqns_error_payload(
                                    message=str(exc),
                                    status_code=422,
                                    retryable=False,
                                    user_message="Произошла ошибка при поиске записей клиента.",
                                )
                            except SQNSClientError as exc:
                                msg = str(exc)
                                status_code = _parse_sqns_status_code(msg)
                                return _sqns_error_payload(
                                    message=msg,
                                    status_code=status_code,
                                    retryable=False if status_code is not None and 400 <= status_code < 500 else True,
                                    user_message="Произошла ошибка при поиске записей клиента.",
                                )
                            except Exception as exc:
                                msg = str(exc)
                                logger.error(
                                    "sqns_list_visits_error",
                                    tool_name=tool_name,
                                    phone=phone,
                                    error=msg,
                                )
                                return _sqns_error_payload(
                                    message=msg,
                                    status_code=_parse_sqns_status_code(msg),
                                    retryable=True,
                                    user_message="Произошла ошибка при поиске записей клиента.",
                                )

                        if method_name == "find_client_by_phone":
                            payload = await method(**kwargs)
                            return _strip_client_visit_field(payload)

                        return await method(**kwargs)

                    except ToolExecutionError:
                        raise
                    except Exception as exc:
                        logger.error("sqns_method_error", method=method_name, error=str(exc))
                        raise ToolExecutionError(f"SQNS error: {str(exc)}") from exc

            _sqns_impl.__name__ = _safe_identifier(tool_name)
            _sqns_impl.__doc__ = description

            return PydanticTool.from_schema(
                function=_sqns_impl,
                name=tool_name,
                description=description,
                json_schema=schema,
                takes_ctx=False,
            )

        tool_fn = make_sqns_tool(defn["method"], defn["name"], defn["description"], defn["schema"])
        tools.append(tool_fn)

    return tools


async def prepare_sqns_tooling(
    agent: Agent,
    user: AuthContext,
) -> tuple[list[Any], list[PydanticTool]]:
    from app.schemas.agent import get_sqns_tools_definitions

    sqns_toolsets: list[Any] = []
    sqns_tools: list[PydanticTool] = []

    if not (agent.sqns_enabled and agent.sqns_host and agent.sqns_credential_id):
        return sqns_toolsets, sqns_tools

    available_names = {
        str(item.get("name"))
        for item in get_sqns_tools_definitions()
        if isinstance(item, dict)
    }
    disabled_tools = {
        str(item).strip()
        for item in (agent.sqns_disabled_tools or [])
        if str(item).strip() and str(item).strip() in available_names
    }
    custom_descriptions = {
        str(key).strip(): str(value).strip()
        for key, value in (agent.sqns_tool_descriptions or {}).items()
        if str(key).strip() in available_names and str(value).strip()
    }

    try:
        # FastMCP currently exposes all registered tools from SQNS MCP server.
        # If any tools are disabled or descriptions are customized per-agent,
        # switch to legacy tool registration where we can include overrides.
        if FASTMCP_AVAILABLE and not disabled_tools and not custom_descriptions:
            sqns_toolset = await _build_sqns_toolset(agent, user)
            sqns_toolsets.append(sqns_toolset)
            logger.info(
                "sqns_toolset_prepared",
                agent_id=str(agent.id),
                approach="fastmcp",
                toolset_type=type(sqns_toolset).__name__,
            )
        else:
            sqns_tools = build_sqns_legacy_tools(agent, user)
    except Exception as exc:
        logger.error("sqns_tools_error", agent_id=str(agent.id), error=str(exc))

    return sqns_toolsets, sqns_tools
