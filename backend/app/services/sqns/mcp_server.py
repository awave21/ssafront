"""
SQNS MCP Server - Интеграция SQNS CRM через Model Context Protocol (MCP).

Этот модуль создает MCP сервер для SQNS, который может быть использован
с pydantic-ai через FastMCPToolset вместо хардкода tool definitions.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Any
from uuid import UUID
import re
from fastmcp import FastMCP
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsResource
from app.services.sqns.client import SQNSClient
from app.utils.phone import normalize_phone_number
from app.services.sqns.sync import SQNSSyncService
from app.schemas.sqns_service import BookingOptionsInput
from app.services.sqns.tool_texts import get_sqns_tool_description

logger = structlog.get_logger(__name__)

_SQNS_STATUS_RE = re.compile(r"\s(?P<status>\d{3}):")
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
    # SQNSClientError формат: "{path} {status}: {response.text}"
    m = _SQNS_STATUS_RE.search(message or "")
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


def _normalize_slots_date(date_value: str) -> str:
    normalized_date = _normalize_date(date_value, "date")
    today = date_cls.today().isoformat()
    if normalized_date < today:
        raise ValueError(
            f"date не может быть в прошлом: {normalized_date}. "
            f"Используй дату не раньше текущей ({today})."
        )
    return normalized_date


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
    client: SQNSClient,
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


def create_sqns_mcp_server(
    client: SQNSClient,
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
) -> FastMCP:
    """
    Создать FastMCP сервер для SQNS CRM интеграции.
    
    Args:
        client: Настроенный SQNS клиент
        db: Async SQLAlchemy сессия для доступа к кэшу
        tenant_id: ID тенанта
        agent_id: ID агента
    
    Returns:
        FastMCP сервер с зарегистрированными тулами для работы с SQNS
    
    Example:
        ```python
        sqns_client = SQNSClient(host="...", api_key="...")
        mcp_server = create_sqns_mcp_server(sqns_client, db, tenant_id, agent_id)
        
        # Использование с pydantic-ai
        from pydantic_ai.toolsets.fastmcp import FastMCPToolset
        toolset = FastMCPToolset(mcp_server)
        agent = Agent(model, toolsets=[toolset])
        ```
    """
    mcp = FastMCP("SQNS CRM Integration")
    
    # Create sync service for smart search and validation
    sync_service = SQNSSyncService(db, client, agent_id)
    
    # ========================================================================
    # ГЛАВНЫЙ ИНСТРУМЕНТ - ИСПОЛЬЗУЙ СНАЧАЛА ЕГО!
    # ========================================================================
    
    @mcp.tool(description=get_sqns_tool_description("sqns_find_booking_options"))
    async def sqns_find_booking_options(
        service_name: str | None = None,
        specialist_name: str | None = None,
    ) -> dict[str, Any]:
        """
        🎯 ГЛАВНЫЙ ИНСТРУМЕНТ для поиска услуг и специалистов.
        Используй СНАЧАЛА этот инструмент, чтобы найти нужную услугу/специалиста
        и получить готовые ID для вызова sqns_list_slots.
        
        Этот инструмент автоматически:
        - Ищет услуги/специалистов по названию (нечеткий поиск)
        - Проверяет совместимость услуги и специалиста
        - Предлагает альтернативы, если выбор несовместим
        - Возвращает готовые service_id и resource_id для записи
        
        Примеры использования:
        1. Клиент: "Хочу записаться на чистку зубов"
           → sqns_find_booking_options(service_name="чистка")
           → Вернет список специалистов, которые делают чистку
        
        2. Клиент: "Хочу к доктору Иванову"
           → sqns_find_booking_options(specialist_name="Иванов")
           → Вернет список услуг доктора Иванова
        
        3. Клиент: "Чистку зубов у Иванова"
           → sqns_find_booking_options(service_name="чистка", specialist_name="Иванов")
           → Проверит совместимость и вернет ID для записи, или предложит альтернативы
        
        4. Клиент: "Какие услуги есть?"
           → sqns_find_booking_options()
           → Вернет топ-20 популярных услуг
        
        Args:
            service_name: Название услуги (например: "чистка", "отбеливание", "консультация").
                         Поиск нечеткий - "чистка" найдет "Профессиональная чистка зубов".
            specialist_name: Имя специалиста (например: "Иванов", "Петрова").
                            Поиск нечеткий - "Иванов" найдет "Иванов Иван Иванович".
        
        Returns:
            - ready: bool - Готово ли для вызова sqns_list_slots
            - service_id: int | None - external_id услуги для sqns_list_slots (используй ЭТО поле, если ready=True)
            - resource_id: int | None - external_id специалиста для sqns_list_slots (используй ЭТО поле, если ready=True)
            - message: str - Понятное описание для клиента
            - alternatives: dict - Альтернативные варианты (если ready=False, используй id из выбранного элемента)
        
        КРИТИЧЕСКИ ВАЖНО - Как использовать результат:
        
        1. Если ready=True:
           - Используй service_id и resource_id из КОРНЯ ответа (не из alternatives!)
           - Вызывай: sqns_list_slots(resource_id=resource_id, date="YYYY-MM-DD", service_ids=[service_id])
        
        2. Если ready=False и есть alternatives:
           - Клиент должен выбрать вариант из alternatives
           - Используй поле "id" из выбранного элемента (это external_id для SQNS API)
           - Если выбрана услуга: service_ids=[выбранный_id]
           - Если выбран специалист: resource_id=выбранный_id
           - Затем снова вызови sqns_find_booking_options с выбранными параметрами
        
        3. ВСЕГДА используй external_id (число), НЕ внутренний UUID!
           - Правильно: service_id=1, resource_id=15
           - Неправильно: service_id="uuid-123" или service_id из другого поля
        """
        try:
            input_data = BookingOptionsInput(
                service_name=service_name,
                specialist_name=specialist_name,
            )
            result = await sync_service.find_booking_options(input_data)
            return result.model_dump()
        except Exception as exc:
            logger.error("sqns_find_booking_options_error", error=str(exc))
            raise
    
    # ========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ ИНСТРУМЕНТЫ (используй редко, обычно достаточно sqns_find_booking_options)
    # ========================================================================
    
    @mcp.tool(description=get_sqns_tool_description("sqns_list_resources"))
    async def sqns_list_resources() -> list[dict[str, Any]]:
        """
        ⚠️ РЕКОМЕНДУЕТСЯ использовать sqns_find_booking_options вместо этого инструмента!
        
        Возвращает список активных специалистов из локального кэша БД.
        Используй ТОЛЬКО если sqns_find_booking_options не подходит.
        
        Returns:
            Список активных сотрудников с resource_id, именами, специализацией.
        """
        try:
            stmt = (
                select(SqnsResource)
                .where(
                    SqnsResource.agent_id == agent_id,
                    SqnsResource.is_active == True,
                    SqnsResource.active == True,
                )
                .order_by(SqnsResource.name)
            )
            result = await db.execute(stmt)
            resources = result.scalars().all()
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
        except Exception as exc:
            logger.error("sqns_list_resources_error", error=str(exc))
            raise
    
    @mcp.tool(description=get_sqns_tool_description("sqns_list_services"))
    async def sqns_list_services() -> list[dict[str, Any]]:
        """
        ⚠️ РЕКОМЕНДУЕТСЯ использовать sqns_find_booking_options вместо этого инструмента!
        
        Возвращает ПОЛНЫЙ список всех услуг (может быть 500+ записей).
        Используй ТОЛЬКО если sqns_find_booking_options не подходит.
        
        Returns:
            Список всех услуг с service_id, названием, длительностью и ценой.
        """
        try:
            result = await client.list_services()
            # Извлекаем массив, если обернут в объект
            if isinstance(result, dict) and 'services' in result:
                return result['services']
            return result if isinstance(result, list) else []
        except Exception as exc:
            logger.error("sqns_list_services_error", error=str(exc))
            raise
    
    @mcp.tool(description=get_sqns_tool_description("sqns_find_client"))
    async def sqns_find_client(phone: str) -> dict[str, Any]:
        """
        Вызывай перед созданием новой записи или когда нужно получить ФИО/контакты клиента.
        Для поиска визитов по телефону/дате используй sqns_client_visits (предпочтительно)
        или sqns_list_visits, а не этот инструмент.
        
        Args:
            phone: Телефон клиента в любом формате (с кодом страны или без, с пробелами/дефисами).
                   Примеры: +79001234567, 8-900-123-45-67, 9001234567.
        
        Returns:
            Данные клиента (ФИО/контакты), либо пустой результат, если клиента нет.
        """
        try:
            payload = await client.find_client_by_phone(phone)
            return _strip_client_visit_field(payload)
        except Exception as exc:
            logger.error("sqns_find_client_error", phone=phone, error=str(exc))
            raise
    
    @mcp.tool(description=get_sqns_tool_description("sqns_list_slots"))
    async def sqns_list_slots(
        resource_id: int,
        date: str,
        service_ids: list[int]
    ) -> dict[str, Any]:
        """
        Вызывай, когда клиент хочет узнать свободное время для записи,
        когда нужно проверить доступность специалиста на конкретную дату,
        или перед созданием записи, чтобы выбрать подходящий временной слот.
        
        ВАЖНО: 
        - resource_id и service_ids должны быть external_id из SQNS API (не внутренние UUID)
        - service_ids - это МАССИВ чисел, даже если услуга одна: [1], а не просто 1
        - Если получил service_id из sqns_find_booking_options, используй его так: service_ids=[service_id]
        
        Args:
            resource_id: external_id специалиста (из sqns_find_booking_options или sqns_list_resources). Обязательный параметр.
            date: Дата в формате YYYY-MM-DD (например, 2026-01-29). Обязательный параметр.
            service_ids: МАССИВ external_id услуг (из sqns_find_booking_options или sqns_list_services). 
                        Даже для одной услуги передавай массив: [1], а не просто 1. Обязательный параметр.
        
        Returns:
            Список слотов с началом/окончанием.
        """
        try:
            normalized_date = _normalize_slots_date(date)

            # Валидация: убеждаемся, что service_ids - это список
            if not isinstance(service_ids, list):
                raise ValueError(f"service_ids must be a list, got {type(service_ids)}: {service_ids}")
            if not service_ids:
                raise ValueError("service_ids cannot be empty")
            
            logger.info(
                "sqns_list_slots_called",
                resource_id=resource_id,
                date=normalized_date,
                service_ids=service_ids,
                service_ids_type=type(service_ids).__name__
            )
            
            return await client.list_slots(
                resource_id=resource_id,
                date=normalized_date,
                service_ids=service_ids
            )
        except ValueError as exc:
            return _sqns_error_payload(
                message=str(exc),
                status_code=422,
                retryable=False,
                user_message="Дата для поиска слотов должна быть сегодня или в будущем.",
            )
        except Exception as exc:
            msg = str(exc)
            status = _parse_sqns_status_code(msg)
            if status is not None and 400 <= status < 500:
                return _sqns_error_payload(message=msg, status_code=status, retryable=False)
            logger.error(
                "sqns_list_slots_error",
                resource_id=resource_id,
                date=date,
                service_ids=service_ids,
                error=msg,
                error_type=type(exc).__name__,
            )
            raise
    
    @mcp.tool(description=get_sqns_tool_description("sqns_create_visit"))
    async def sqns_create_visit(
        resource_id: int,
        service_id: int,
        datetime: str,
        user_name: str,
        phone: str,
        email: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """
        Вызывай, когда клиент хочет записаться на прием к специалисту.
        client_id не требуется: визит создаётся по user.name + user.phone. Если есть клиент с таким
        телефоном, визит привяжется к нему; иначе SQNS создаст клиента при создании визита.
        Перед созданием записи всегда: sqns_find_client (ФИО/телефон), sqns_list_resources,
        sqns_list_services, sqns_list_slots.
        
        Args:
            resource_id: ID специалиста из sqns_list_resources. Обязательный параметр.
            service_id: ID услуги из sqns_list_services. Обязательный параметр.
            datetime: Дата и время в формате ISO 8601 (например, 2026-01-25T14:00:00+05:00).
                     Только из свободных слотов (sqns_list_slots). Обязательный параметр.
            user_name: ФИО клиента (из sqns_find_client или от пользователя). Обязателен.
            phone: Телефон клиента (из sqns_find_client или от пользователя). Обязателен.
            email: Email клиента. Необязателен, можно не передавать.
            comment: Комментарий к записи (например, "Первичный прием"). Опционально.
        
        Returns:
            Созданная запись с visit_id и деталями визита.
        """
        try:
            name = (user_name or "").strip()
            if not name:
                raise ValueError(
                    "user_name обязателен. Получи из sqns_find_client (client.name) или от пользователя."
                )
            raw_phone = (phone or "").strip()
            if not raw_phone:
                raise ValueError(
                    "phone обязателен. Получи из sqns_find_client (client.phone) или от пользователя."
                )
            normalized_phone = normalize_phone_number(raw_phone)
            user_obj: dict[str, Any] = {"name": name, "phone": normalized_phone}
            if email and (e := (email or "").strip()):
                user_obj["email"] = e
            visit_payload: dict[str, Any] = {
                "user": user_obj,
                "appointment": {
                    "serviceIds": [str(service_id)],
                    "resourceId": str(resource_id),
                    "datetime": datetime,
                },
            }
            if comment and (c := (comment or "").strip()):
                visit_payload["comment"] = c
            
            return await client.create_visit(visit_payload)
        except ValueError:
            raise
        except Exception as exc:
            # Best practice: 4xx валидация = НЕ ретраить, а вернуть структурированную ошибку,
            # чтобы агент задал уточняющие вопросы пользователю.
            msg = str(exc)
            status = _parse_sqns_status_code(msg)
            if status is not None and 400 <= status < 500:
                return _sqns_error_payload(message=msg, status_code=status, retryable=False)
            logger.error("sqns_create_visit_error", error=msg)
            raise
    
    @mcp.tool(description=get_sqns_tool_description("sqns_update_visit"))
    async def sqns_update_visit(
        visit_id: int,
        datetime: str | None = None,
        comment: str | None = None,
        status: str | None = None
    ) -> dict[str, Any]:
        """
        Вызывай, когда клиент хочет перенести запись на другое время,
        когда нужно добавить или изменить комментарий к записи,
        или когда требуется изменить статус визита (подтвердить, отменить, отметить как выполненный).
        
        Args:
            visit_id: ID записи для обновления. Получи из sqns_list_visits или из результата sqns_create_visit.
                     Обязательный параметр.
            datetime: Новая дата и время приема в формате ISO 8601 (например, "2026-01-26T10:00:00").
                     Используй, если клиент хочет перенести запись. Проверь свободные слоты через sqns_list_slots.
            comment: Новый или дополнительный комментарий к записи.
            status: Новый статус визита (например, "confirmed", "cancelled", "completed").
        
        Returns:
            Обновленная запись со всеми деталями.
        """
        try:
            payload: dict[str, Any] = {}
            if datetime:
                payload["datetime"] = datetime
            if comment:
                payload["comment"] = comment
            if status:
                payload["status"] = status
            
            return await client.update_visit(visit_id, payload)
        except Exception as exc:
            msg = str(exc)
            status_code = _parse_sqns_status_code(msg)
            if status_code is not None and 400 <= status_code < 500:
                return _sqns_error_payload(message=msg, status_code=status_code, retryable=False)
            logger.error("sqns_update_visit_error", visit_id=visit_id, error=msg)
            raise
    
    @mcp.tool(description=get_sqns_tool_description("sqns_list_visits"))
    async def sqns_list_visits(
        phone: str,
        date_from: str,
        date_till: str,
        per_page: int = 100,
    ) -> dict[str, Any]:
        """
        Вызывай, когда клиент хочет посмотреть свои записи или историю визитов,
        когда нужно найти конкретную запись для обновления или отмены,
        или когда требуется просмотреть расписание за определенный период.
        
        Args:
            date_from: Начальная дата периода в формате YYYY-MM-DD (например, "2026-01-25").
                      Обязательный параметр.
            date_till: Конечная дата периода в формате YYYY-MM-DD (например, "2026-01-31").
                      Обязательный параметр.
            per_page: Количество записей на страницу (по умолчанию 100, максимум 100).
        
        Returns:
            Список визитов с деталями: visit_id, client, resource, service, datetime, status, comment.
        """
        try:
            normalized_phone = normalize_phone_number(phone)
            normalized_date_from = _normalize_date(date_from, "date_from")
            normalized_date_till = _normalize_date(date_till, "date_till")
            safe_per_page = _normalize_per_page(per_page)
            if normalized_date_from > normalized_date_till:
                raise ValueError("date_from не может быть позже date_till.")

            # 1) Проверяем клиента (и не даём модели работать "вслепую")
            client_payload = _strip_client_visit_field(
                await client.find_client_by_phone(normalized_phone)
            )

            # 2) SQNS endpoint /api/v2/visit возвращает визиты за период без фильтра по клиенту.
            # Поэтому мы фильтруем ответ строго по телефону клиента, чтобы не отдавать чужие визиты модели.
            raw_visits, visits_payload, pagination = await _collect_visits_pages(
                client,
                date_from=normalized_date_from,
                date_till=normalized_date_till,
                per_page=safe_per_page,
            )
            filtered_visits = _filter_visits_by_phone(raw_visits, normalized_phone)
            logger.info(
                "sqns_list_visits_filtered",
                phone=normalized_phone,
                date_from=normalized_date_from,
                date_till=normalized_date_till,
                raw_count=len(raw_visits),
                filtered_count=len(filtered_visits),
                pages_scanned=pagination.get("pages_scanned"),
                last_page=pagination.get("last_page"),
            )

            # Возвращаем только отфильтрованные визиты + служебную инфу
            if isinstance(visits_payload, dict):
                safe_payload = _set_filtered_visits(visits_payload, filtered_visits)
                safe_payload["client"] = client_payload.get("client") if isinstance(client_payload, dict) else client_payload
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
        except Exception as exc:
            msg = str(exc)
            status_code = _parse_sqns_status_code(msg)
            if status_code is not None and 400 <= status_code < 500:
                return _sqns_error_payload(
                    message=msg,
                    status_code=status_code,
                    retryable=False,
                    user_message="Произошла ошибка при поиске записей клиента.",
                )
            logger.error(
                "sqns_list_visits_error",
                phone=phone,
                date_from=date_from,
                date_till=date_till,
                error=msg,
            )
            return _sqns_error_payload(
                message=msg,
                status_code=status_code,
                retryable=True,
                user_message="Произошла ошибка при поиске записей клиента.",
            )

    @mcp.tool(description=get_sqns_tool_description("sqns_client_visits"))
    async def sqns_client_visits(
        phone: str,
        date: str | None = None,
        date_from: str | None = None,
        date_till: str | None = None,
        per_page: int = 100,
    ) -> dict[str, Any]:
        """
        Вызывай, когда нужно найти запись конкретного клиента для переноса или отмены.
        Инструмент принимает телефон и дату (один день или диапазон) и возвращает только
        компактный список подходящих визитов без сырого payload SQNS.
        Отдельно вызывать sqns_find_client перед этим инструментом не нужно.

        Args:
            phone: Телефон клиента в любом формате.
            date: Одна дата в формате YYYY-MM-DD.
            date_from: Начало диапазона в формате YYYY-MM-DD.
            date_till: Конец диапазона в формате YYYY-MM-DD.
            per_page: Количество записей на страницу (от 1 до 100).

        Returns:
            Компактные визиты клиента: phone, date_filter, count, visits.
        """
        try:
            normalized_phone = normalize_phone_number(phone)
            normalized_date_from, normalized_date_till, date_filter = _resolve_visits_period(
                date=date,
                date_from=date_from,
                date_till=date_till,
            )
            safe_per_page = _normalize_per_page(per_page)

            # Проверяем клиента перед фильтрацией, чтобы не работать "вслепую".
            await client.find_client_by_phone(normalized_phone)

            raw_visits, _, pagination = await _collect_visits_pages(
                client,
                date_from=normalized_date_from,
                date_till=normalized_date_till,
                per_page=safe_per_page,
            )
            filtered_visits = _filter_visits_by_phone(raw_visits, normalized_phone)

            resource_name_by_id: dict[str, str] = {}
            try:
                resources_payload = await client.list_resources()
                resource_name_by_id = _extract_resource_name_map(resources_payload)
            except Exception as exc:
                # Best effort: если список специалистов недоступен, возвращаем compact без resource_name.
                logger.warning("sqns_client_visits_resource_map_error", error=str(exc))

            compact_visits = [_compact_visit(visit, resource_name_by_id) for visit in filtered_visits]

            logger.info(
                "sqns_client_visits_filtered",
                phone=normalized_phone,
                date_from=normalized_date_from,
                date_till=normalized_date_till,
                raw_count=len(raw_visits),
                filtered_count=len(filtered_visits),
                pages_scanned=pagination.get("pages_scanned"),
                last_page=pagination.get("last_page"),
            )

            return {
                "phone": normalized_phone,
                "date_filter": date_filter,
                "count": len(compact_visits),
                "visits": compact_visits,
                "message": _build_visits_message(len(compact_visits)),
            }
        except ValueError as exc:
            return _sqns_error_payload(
                message=str(exc),
                status_code=422,
                retryable=False,
                user_message="Произошла ошибка при поиске записей клиента.",
            )
        except Exception as exc:
            msg = str(exc)
            status_code = _parse_sqns_status_code(msg)
            if status_code is not None and 400 <= status_code < 500:
                return _sqns_error_payload(
                    message=msg,
                    status_code=status_code,
                    retryable=False,
                    user_message="Произошла ошибка при поиске записей клиента.",
                )
            logger.error(
                "sqns_client_visits_error",
                phone=phone,
                date=date,
                date_from=date_from,
                date_till=date_till,
                error=msg,
            )
            return _sqns_error_payload(
                message=msg,
                status_code=status_code,
                retryable=True,
                user_message="Произошла ошибка при поиске записей клиента.",
            )
    
    @mcp.tool(description=get_sqns_tool_description("sqns_delete_visit"))
    async def sqns_delete_visit(visit_id: int) -> dict[str, Any]:
        """
        Вызывай, когда клиент хочет отменить запись,
        когда запись была создана по ошибке,
        или когда требуется полностью удалить визит из системы.
        ВНИМАНИЕ: Это действие необратимо - запись будет удалена из системы.
        
        Args:
            visit_id: ID записи для удаления. Получи из sqns_list_visits или из результата sqns_create_visit.
                     Обязательный параметр.
        
        Returns:
            {"ok": true} при успешном удалении, либо {"ok": false, ...} при валидационной ошибке.
        """
        try:
            await client.delete_visit(visit_id)
            logger.info("sqns_visit_deleted", visit_id=visit_id)
            return {"ok": True}
        except Exception as exc:
            msg = str(exc)
            status_code = _parse_sqns_status_code(msg)
            if status_code is not None and 400 <= status_code < 500:
                return _sqns_error_payload(message=msg, status_code=status_code, retryable=False)
            logger.error("sqns_delete_visit_error", visit_id=visit_id, error=msg)
            raise
    
    # FastMCP может не иметь _tools в зависимости от версии
    tool_count = len(getattr(mcp, '_tools', [])) or len(getattr(mcp, 'tools', []))
    logger.info("sqns_mcp_server_created", tool_count=tool_count)
    
    return mcp
