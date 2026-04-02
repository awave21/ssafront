"""Service for synchronizing SQNS data to local database cache."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import re
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.db.models.sqns_service import (
    SqnsResource,
    SqnsService,
    SqnsServiceResource,
    SqnsServiceCategory,
)
from app.schemas.sqns_service import (
    BookingAlternative,
    BookingOptionsInput,
    BookingOptionsOutput,
    SyncResult,
)
from app.services.sqns.client import SQNSClient
from app.services.sqns.sync_handlers.employees import _service_external_ids_from_employee
from app.services.sqns.sync_handlers.services import (
    SqnsServicesSyncHandler,
    collect_resource_refs_from_services_payload,
    collect_service_resource_links,
    load_booking_resources_by_service_external_id,
    merge_service_payload_from_booking_api,
    resource_data_from_service_link,
)
from app.services.sqns.sync_orchestrator import SqnsSyncOrchestrator

logger = structlog.get_logger(__name__)

# Единый лимит выдачи для sqns_find_booking_options (услуги, врачи, пары).
BOOKING_OPTIONS_RESULT_LIMIT = 50


class SQNSSyncService:
    """
    Сервис для синхронизации данных из SQNS API в локальный кэш PostgreSQL.
    
    Реализует умную логику поиска, валидации и предоставления альтернатив
    для композитного инструмента sqns_find_booking_options.
    """

    def __init__(self, db: AsyncSession, sqns_client: SQNSClient, agent_id: UUID):
        self.db = db
        self.sqns_client = sqns_client
        self.agent_id = agent_id

    def _service_category_matches(self, category: str) -> Any:
        """
        Подстрока категории: колонка category, совпадение с именами из справочника категорий,
        типичные ключи в raw_data SQNS (часто category заполнен только в JSON).
        """
        pat = f"%{category}%"
        rd = SqnsService.raw_data
        canonical = select(SqnsServiceCategory.name).where(
            SqnsServiceCategory.agent_id == self.agent_id,
            SqnsServiceCategory.name.ilike(pat),
        )
        return or_(
            SqnsService.category.ilike(pat),
            SqnsService.category.in_(canonical),
            rd["categoryName"].astext.ilike(pat),
            rd["category"].astext.ilike(pat),
            rd["category"]["name"].astext.ilike(pat),
        )

    def _booking_service_predicates(self, *, category: str | None) -> list[Any]:
        """
        Условия для выборки услуг в sqns_find_booking_options: активная услуга,
        категория не отключена в sqns_service_categories, опционально ILIKE по category.
        """
        category_disabled = exists(
            select(1).where(
                SqnsServiceCategory.agent_id == self.agent_id,
                SqnsServiceCategory.name == SqnsService.category,
                SqnsServiceCategory.is_enabled.is_(False),
            )
        )
        preds: list[Any] = [
            SqnsService.agent_id == self.agent_id,
            SqnsService.is_enabled.is_(True),
            or_(
                SqnsService.category.is_(None),
                SqnsService.category == "",
                ~category_disabled,
            ),
        ]
        if category:
            preds.append(self._service_category_matches(category))
        return preds

    async def _list_booking_services(self, *, category: str | None = None) -> list[SqnsService]:
        """Активные услуги из кэша с теми же предикатами, что и в find_booking_options."""
        stmt = (
            select(SqnsService)
            .where(and_(*self._booking_service_predicates(category=category)))
            .order_by(SqnsService.priority.desc(), SqnsService.name)
            .limit(BOOKING_OPTIONS_RESULT_LIMIT)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _services_to_booking_alternatives(services: list[SqnsService]) -> list[BookingAlternative]:
        return [
            BookingAlternative(
                id=svc.external_id,
                name=svc.name,
                additional_info=(
                    f"{svc.category or 'Без категории'} • {svc.duration_seconds // 60} мин"
                ),
            )
            for svc in services
        ]

    @staticmethod
    def _coerce_number(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float, Decimal)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            normalized = text.replace(" ", "").replace(",", ".")
            try:
                return float(normalized)
            except ValueError:
                cleaned = re.sub(r"[^0-9.+-]", "", normalized)
                if not cleaned:
                    return None
                try:
                    return float(cleaned)
                except ValueError:
                    return None
        if isinstance(value, dict):
            for key in (
                "value",
                "amount",
                "price",
                "sum",
                "total",
                "from",
                "min",
                "range",
                "minPrice",
                "min_price",
            ):
                if key in value:
                    candidate = SQNSSyncService._coerce_number(value.get(key))
                    if candidate is not None:
                        return candidate
            if len(value) == 1:
                return SQNSSyncService._coerce_number(next(iter(value.values())))
            return None
        if isinstance(value, (list, tuple)):
            for item in value:
                candidate = SQNSSyncService._coerce_number(item)
                if candidate is not None:
                    return candidate
            return None
        return None

    @classmethod
    def _parse_price(cls, value: Any) -> float | None:
        return cls._coerce_number(value)

    @classmethod
    def _parse_duration_seconds(cls, value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, dict):
            unit = value.get("unit") or value.get("units")
            if unit:
                unit_label = str(unit).lower()
                number = cls._coerce_number(
                    value.get("value")
                    or value.get("amount")
                    or value.get("duration")
                    or value.get("seconds")
                    or value.get("minutes")
                    or value.get("hours")
                )
                if number is None:
                    return 0
                if "min" in unit_label:
                    return int(number * 60)
                if "hour" in unit_label or "hr" in unit_label:
                    return int(number * 3600)
                return int(number)
            if "durationMinutes" in value or "minutes" in value:
                number = cls._coerce_number(value.get("durationMinutes") or value.get("minutes"))
                if number is not None:
                    return int(number * 60)
            if "durationHours" in value or "hours" in value:
                number = cls._coerce_number(value.get("durationHours") or value.get("hours"))
                if number is not None:
                    return int(number * 3600)
        number = cls._coerce_number(value)
        return int(number) if number is not None else 0

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)

    @staticmethod
    def _compose_employee_name(employee: dict[str, Any]) -> str | None:
        parts = []
        for key in ("lastname", "firstname", "patronymic"):
            raw_value = employee.get(key)
            if raw_value is None:
                continue
            value = str(raw_value).strip()
            if value:
                parts.append(value)
        if parts:
            return " ".join(parts)
        for key in ("name", "fullName", "title", "fio", "displayName"):
            raw_value = employee.get(key)
            if raw_value is None:
                continue
            value = str(raw_value).strip()
            if value:
                return value
        return None

    def _normalize_employee_resource(
        self,
        employee: dict[str, Any],
    ) -> tuple[int, dict[str, Any]] | None:
        if "id" not in employee:
            return None
        try:
            external_id = int(employee["id"])
        except (TypeError, ValueError):
            logger.warning(
                "sqns_employee_invalid_id",
                agent_id=str(self.agent_id),
                employee_id=employee.get("id"),
            )
            return None

        name = self._compose_employee_name(employee)
        specialization = (
            employee.get("position")
            or employee.get("specialization")
            or employee.get("specialty")
            or employee.get("role")
        )
        is_fired = self._coerce_bool(employee.get("isFired", False))
        is_deleted = self._coerce_bool(employee.get("isDeleted", False))
        is_active = not is_fired and not is_deleted

        resource_data = dict(employee)
        if name:
            resource_data["name"] = name
        if specialization:
            resource_data["specialization"] = specialization
        resource_data["isActive"] = is_active
        return external_id, resource_data

    def _build_resources_map_from_employees(
        self,
        employees: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        resources_map: dict[int, dict[str, Any]] = {}
        for employee in employees:
            if not isinstance(employee, dict):
                continue
            normalized = self._normalize_employee_resource(employee)
            if normalized is None:
                continue
            external_id, resource_data = normalized
            resources_map[external_id] = resource_data
        return resources_map

    async def _mark_stale_resources_inactive(
        self,
        active_external_ids: set[int],
        synced_at: datetime,
    ) -> int:
        stmt = (
            update(SqnsResource)
            .where(
                SqnsResource.agent_id == self.agent_id,
                SqnsResource.is_active == True,
            )
            .values(
                is_active=False,
                synced_at=synced_at,
                updated_at=synced_at,
            )
        )
        if active_external_ids:
            stmt = stmt.where(SqnsResource.external_id.notin_(active_external_ids))

        result = await self.db.execute(stmt)
        return result.rowcount or 0

    async def sync_services(self) -> SyncResult:
        """
        Синхронизирует услуги, специалистов и категории из SQNS API в локальный кэш.
        
        Алгоритм:
        1. Fetch services from SQNS API
        2. Extract unique resources (specialists) → upsert sqns_resources
        3. Upsert services → sqns_services
        4. Extract categories → upsert sqns_service_categories
        5. Sync M2M links → sqns_service_resources (delete old, insert new)
        6. Mark stale resources as inactive (not in response)
        
        Returns:
            SyncResult с количеством синхронизированных записей
        """
        try:
            logger.info("sqns_sync_started", agent_id=str(self.agent_id))
            
            # 1. Fetch data from SQNS API
            services_response = await self.sqns_client.list_services()
            
            # SQNS API может вернуть список напрямую или обернутым в {"services": [...]}
            if isinstance(services_response, dict) and "services" in services_response:
                services_data = services_response["services"]
            elif isinstance(services_response, list):
                services_data = services_response
            else:
                logger.error("sqns_invalid_format", agent_id=str(self.agent_id), response_type=type(services_response).__name__)
                return SyncResult(
                    success=False,
                    message="SQNS API returned invalid data format",
                    errors=[f"Expected list or dict with 'services', got {type(services_response).__name__}"],
                )

            synced_at = datetime.now(timezone.utc)
            resources_count = 0
            services_count = 0
            categories_count = 0
            links_count = 0
            stale_resources_count = 0

            employees = await self.sqns_client.list_all_employees(
                per_page=100,
                is_fired=0,
                is_deleted=0,
            )
            resources_map = self._build_resources_map_from_employees(employees)

            booking_resources_by_id = await load_booking_resources_by_service_external_id(self.sqns_client)
            resource_ids_from_services, link_by_resource_id = await collect_resource_refs_from_services_payload(
                self.sqns_client,
                services_data,
                booking_resources_by_id,
            )

            # 2. Upsert resources (specialists) из списка сотрудников
            synced_resource_external_ids: set[int] = set()
            for external_id, resource_data in resources_map.items():
                await self._upsert_resource(external_id, resource_data, synced_at)
                synced_resource_external_ids.add(external_id)
                resources_count += 1

            # Специалисты только из онлайн-записи (resources услуги), но не в /employee — не помечаем устаревшими
            employee_external_ids = set(synced_resource_external_ids)
            for ext_res in resource_ids_from_services:
                if ext_res in employee_external_ids:
                    continue
                link = link_by_resource_id.get(ext_res, {})
                stub = resource_data_from_service_link(ext_res, link)
                await self._upsert_resource(ext_res, stub, synced_at)
                synced_resource_external_ids.add(ext_res)
                resources_count += 1
                logger.info(
                    "sqns_resource_upserted_from_service_link",
                    agent_id=str(self.agent_id),
                    external_id=ext_res,
                )

            protected_resource_ids = employee_external_ids | resource_ids_from_services
            stale_resources_count = await self._mark_stale_resources_inactive(
                protected_resource_ids,
                synced_at,
            )

            # Build map: external_id -> internal UUID
            resource_stmt = select(SqnsResource.id, SqnsResource.external_id).where(
                SqnsResource.agent_id == self.agent_id,
                SqnsResource.is_active == True,
            )
            result = await self.db.execute(resource_stmt)
            resource_uuid_map = {ext_id: uuid for uuid, ext_id in result.fetchall()}

            # 3. Process each service
            for service in services_data:
                if not isinstance(service, dict) or "id" not in service:
                    continue

                external_id = int(service["id"])

                service = await merge_service_payload_from_booking_api(
                    self.sqns_client,
                    service,
                    external_id,
                    booking_resources_by_id,
                )

                # Upsert service
                service_uuid = await self._upsert_service(external_id, service, synced_at)
                services_count += 1

                # Sync M2M links for this service
                resource_links = collect_service_resource_links(service)
                if resource_links is not None:
                    links_added = await self._sync_service_resources(
                        service_uuid,
                        resource_links,
                        resource_uuid_map,
                    )
                    links_count += links_added

                # Track category
                category = service.get("category") or service.get("categoryName")
                if category and isinstance(category, str):
                    await self._upsert_category(category, synced_at)

            employee_pairs: list[tuple[int, int]] = []
            for employee in employees:
                if not isinstance(employee, dict) or "id" not in employee:
                    continue
                try:
                    emp_ext = int(employee["id"])
                except (TypeError, ValueError):
                    continue
                for svc_ext in _service_external_ids_from_employee(employee):
                    employee_pairs.append((emp_ext, svc_ext))
            if employee_pairs:
                merge_handler = SqnsServicesSyncHandler(self.db, self.sqns_client, self.agent_id)
                links_count += await merge_handler.merge_employee_service_resource_links(
                    employee_pairs,
                    resource_uuid_map,
                    synced_at,
                )

            # 4. Count unique categories synced
            categories_stmt = select(func.count(SqnsServiceCategory.id)).where(
                SqnsServiceCategory.agent_id == self.agent_id
            )
            result = await self.db.execute(categories_stmt)
            categories_count = result.scalar() or 0

            await self.db.commit()

            logger.info(
                "sqns_sync_completed",
                agent_id=str(self.agent_id),
                resources=resources_count,
                services=services_count,
                categories=categories_count,
                links=links_count,
                stale_resources=stale_resources_count,
            )

            return SyncResult(
                success=True,
                message=(
                    f"Синхронизировано: {services_count} услуг, {resources_count} специалистов, "
                    f"{categories_count} категорий; деактивировано {stale_resources_count} неактуальных специалистов"
                ),
                resources_synced=resources_count,
                services_synced=services_count,
                categories_synced=categories_count,
                links_synced=links_count,
                synced_at=synced_at,
            )

        except Exception as exc:
            await self.db.rollback()
            logger.exception("sqns_sync_failed", agent_id=str(self.agent_id), error=str(exc))
            return SyncResult(
                success=False,
                message=f"Ошибка синхронизации: {str(exc)}",
                errors=[str(exc)],
            )

    async def _upsert_resource(
        self,
        external_id: int,
        resource_data: dict[str, Any],
        synced_at: datetime,
    ) -> UUID:
        """Upsert resource (specialist) into sqns_resources."""
        name = (
            resource_data.get("name")
            or resource_data.get("fullName")
            or resource_data.get("title")
            or resource_data.get("fio")
            or resource_data.get("displayName")
            or f"Resource {external_id}"
        )
        specialization = (
            resource_data.get("specialization")
            or resource_data.get("specialty")
            or resource_data.get("position")
            or resource_data.get("role")
        )
        is_active = resource_data.get("isActive", resource_data.get("active", True))

        stmt = insert(SqnsResource).values(
            id=uuid4(),
            agent_id=self.agent_id,
            external_id=external_id,
            name=str(name),
            specialization=str(specialization) if specialization else None,
            is_active=bool(is_active),
            active=True,
            information=None,
            raw_data=resource_data,
            synced_at=synced_at,
            created_at=synced_at,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_sqns_resources_agent_external",
            set_={
                "name": stmt.excluded.name,
                "specialization": stmt.excluded.specialization,
                "is_active": stmt.excluded.is_active,
                "raw_data": stmt.excluded.raw_data,
                "synced_at": stmt.excluded.synced_at,
                "updated_at": synced_at,
            },
        ).returning(SqnsResource.id)

        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _upsert_service(
        self,
        external_id: int,
        service_data: dict[str, Any],
        synced_at: datetime,
    ) -> UUID:
        """Upsert service into sqns_services."""
        name = (
            service_data.get("name")
            or service_data.get("title")
            or service_data.get("serviceName")
            or service_data.get("service")
            or service_data.get("fullName")
            or f"Service {external_id}"
        )
        category = service_data.get("category") or service_data.get("categoryName")
        if isinstance(category, dict):
            category = (
                category.get("name")
                or category.get("title")
                or category.get("label")
                or category.get("value")
            )
        price = self._parse_price(service_data.get("price"))
        duration = self._parse_duration_seconds(
            service_data.get("durationSeconds")
            or service_data.get("duration")
            or service_data.get("durationMinutes")
        )
        description = service_data.get("description") or service_data.get("details") or service_data.get("desc")

        stmt = insert(SqnsService).values(
            id=uuid4(),
            agent_id=self.agent_id,
            external_id=external_id,
            name=str(name),
            category=str(category) if category else None,
            price=price,
            duration_seconds=duration,
            description=str(description) if description else None,
            is_enabled=True,  # По умолчанию включено
            priority=0,       # По умолчанию приоритет 0
            raw_data=service_data,
            synced_at=synced_at,
            created_at=synced_at,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_sqns_services_agent_external",
            set_={
                "name": stmt.excluded.name,
                "category": stmt.excluded.category,
                "price": stmt.excluded.price,
                "duration_seconds": stmt.excluded.duration_seconds,
                "description": stmt.excluded.description,
                "raw_data": stmt.excluded.raw_data,
                "synced_at": stmt.excluded.synced_at,
                "updated_at": synced_at,
                # Сохраняем is_enabled и priority (настройки пользователя)
            },
        ).returning(SqnsService.id)

        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _sync_service_resources(
        self,
        service_uuid: UUID,
        resource_links: list[dict[str, Any]],
        resource_uuid_map: dict[int, UUID],
    ) -> int:
        """
        Синхронизирует связи услуга-специалист.
        
        DELETE старые связи для этой услуги, INSERT новые.
        """
        # Delete existing links for this service
        await self.db.execute(
            delete(SqnsServiceResource).where(
                SqnsServiceResource.service_id == service_uuid
            )
        )

        # Insert new links
        links_to_insert = []
        for link in resource_links:
            if not isinstance(link, dict) or "id" not in link:
                continue
            
            resource_ext_id = int(link["id"])
            resource_uuid = resource_uuid_map.get(resource_ext_id)
            
            if not resource_uuid:
                logger.warning(
                    "sqns_resource_not_found",
                    service_uuid=str(service_uuid),
                    resource_external_id=resource_ext_id,
                )
                continue

            duration_override = self._parse_duration_seconds(
                link.get("durationSeconds") or link.get("duration") or link.get("durationMinutes")
            )
            
            links_to_insert.append({
                "id": uuid4(),
                "service_id": service_uuid,
                "resource_id": resource_uuid,
                "duration_seconds": duration_override if duration_override else None,
                "created_at": datetime.now(timezone.utc),
            })

        if links_to_insert:
            await self.db.execute(insert(SqnsServiceResource), links_to_insert)

        return len(links_to_insert)

    async def _upsert_category(self, category_name: str, synced_at: datetime) -> UUID:
        """Upsert category into sqns_service_categories."""
        stmt = insert(SqnsServiceCategory).values(
            id=uuid4(),
            agent_id=self.agent_id,
            name=category_name,
            is_enabled=True,
            priority=0,
            created_at=synced_at,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_sqns_categories_agent_name",
            set_={
                "updated_at": synced_at,
                # Сохраняем is_enabled и priority (настройки пользователя)
            },
        ).returning(SqnsServiceCategory.id)

        result = await self.db.execute(stmt)
        return result.scalar_one()

    # ========================================================================
    # Smart search and validation methods for sqns_find_booking_options
    # ========================================================================

    async def find_booking_options(
        self,
        input_data: BookingOptionsInput,
    ) -> BookingOptionsOutput:
        """
        Умный поиск опций для бронирования с валидацией и альтернативами.
        
        Сценарии:
        1. service_name only → список специалистов для услуги
        2. specialist_name only → список услуг специалиста
        3. Оба параметра → валидация совместимости + ID для записи
        4. Ничего → топ услуг по priority (см. BOOKING_OPTIONS_RESULT_LIMIT)
        5. category (опционально ко всем сценариям) → фильтр по полю category услуги (ILIKE);
           при пустом совпадении имя+category — fallback: список услуг только по category (если категория не пустая).
        """
        service_name = (input_data.service_name or "").strip() or None
        specialist_name = (input_data.specialist_name or "").strip() or None
        category = (input_data.category or "").strip() or None

        # Сценарий 4: Ничего не указано → топ услуг
        if not service_name and not specialist_name:
            return await self._get_top_services(category=category)

        # Сценарий 2: Только специалист → услуги специалиста
        if specialist_name and not service_name:
            return await self._find_services_by_specialist(specialist_name, category=category)

        # Сценарий 1: Только услуга → специалисты для услуги
        if service_name and not specialist_name:
            return await self._find_specialists_by_service(service_name, category=category)

        # Сценарий 3: Оба параметра → проверка совместимости
        return await self._validate_compatibility(
            service_name,
            specialist_name,
            category=category,
        )

    async def _get_top_services(self, *, category: str | None = None) -> BookingOptionsOutput:
        """Возвращает топ услуг по приоритету (лимит BOOKING_OPTIONS_RESULT_LIMIT)."""
        services = await self._list_booking_services(category=category)

        if not services:
            return BookingOptionsOutput(
                ready=False,
                message=(
                    "Нет доступных услуг по заданным условиям. "
                    "Проверьте категорию (sqns_list_categories) или синхронизируйте данные из SQNS."
                    if category
                    else "Нет доступных услуг. Пожалуйста, синхронизируйте данные из SQNS."
                ),
            )

        alternatives = [
            BookingAlternative(
                id=svc.external_id,
                name=svc.name,
                additional_info=f"{svc.category or 'Без категории'} • {svc.duration_seconds // 60} мин",
            )
            for svc in services
        ]

        msg = f"Доступно {len(services)} услуг. Выберите услугу или специалиста для продолжения."
        if category:
            msg = f"В категории (по фильтру «{category}») доступно {len(services)} услуг. Выберите услугу или специалиста."

        return BookingOptionsOutput(
            ready=False,
            message=msg,
            alternatives={"services": alternatives},
        )

    async def _find_services_by_specialist(
        self,
        specialist_name: str,
        *,
        category: str | None = None,
    ) -> BookingOptionsOutput:
        """Поиск услуг, которые может выполнять специалист."""
        # Поиск специалиста по имени (ILIKE)
        resource_stmt = (
            select(SqnsResource)
            .where(
                SqnsResource.agent_id == self.agent_id,
                SqnsResource.is_active == True,
                SqnsResource.active == True,
                SqnsResource.name.ilike(f"%{specialist_name}%"),
            )
            .limit(1)
        )
        result = await self.db.execute(resource_stmt)
        resource = result.scalar_one_or_none()

        if not resource:
            return BookingOptionsOutput(
                ready=False,
                message=(
                    f"Специалист '{specialist_name}' не найден. Проверьте написание или синхронизируйте данные. "
                    f"Попробуйте использовать sqns_list_resources для просмотра всех доступных специалистов."
                ),
            )

        # Найти услуги этого специалиста
        services_stmt = (
            select(SqnsService)
            .join(
                SqnsServiceResource,
                SqnsServiceResource.service_id == SqnsService.id,
            )
            .where(
                SqnsServiceResource.resource_id == resource.id,
                and_(*self._booking_service_predicates(category=category)),
            )
            .order_by(SqnsService.priority.desc(), SqnsService.name)
            .limit(BOOKING_OPTIONS_RESULT_LIMIT)
        )
        result = await self.db.execute(services_stmt)
        services = result.scalars().all()

        if not services:
            return BookingOptionsOutput(
                ready=False,
                resource_id=resource.external_id,
                resource_name=resource.name,
                message=f"У специалиста {resource.name} нет доступных услуг.",
            )

        alternatives = [
            BookingAlternative(
                id=svc.external_id,
                name=svc.name,
                additional_info=f"{svc.duration_seconds // 60} мин • {svc.price} руб." if svc.price else f"{svc.duration_seconds // 60} мин",
            )
            for svc in services
        ]

        return BookingOptionsOutput(
            ready=False,
            resource_id=resource.external_id,
            resource_name=resource.name,
            message=(
                f"Специалист {resource.name} может выполнить {len(services)} услуг. "
                f"Выберите услугу из списка alternatives.services. "
                f"Используй поле 'id' из выбранной услуги (это external_id для sqns_list_slots)."
            ),
            alternatives={"services": alternatives},
        )

    async def _find_specialists_by_service(
        self,
        service_name: str,
        *,
        category: str | None = None,
    ) -> BookingOptionsOutput:
        """Поиск специалистов по услуге (одна или несколько услуг по ILIKE)."""
        service_stmt = (
            select(SqnsService)
            .where(
                and_(
                    SqnsService.name.ilike(f"%{service_name}%"),
                    *self._booking_service_predicates(category=category),
                ),
            )
            .order_by(SqnsService.priority.desc(), SqnsService.name)
            .limit(BOOKING_OPTIONS_RESULT_LIMIT)
        )
        result = await self.db.execute(service_stmt)
        services = result.scalars().all()

        if not services:
            if category:
                in_category = await self._list_booking_services(category=category)
                if in_category:
                    return BookingOptionsOutput(
                        ready=False,
                        message=(
                            f"По названию «{service_name}» в категории «{category}» услуга не найдена "
                            f"(возможна неточность в названии). Ниже {len(in_category)} услуг в этой категории — "
                            f"выберите подходящую и вызовите sqns_find_booking_options с уточнённым service_name "
                            f"(category можно оставить или убрать)."
                        ),
                        alternatives={
                            "services": self._services_to_booking_alternatives(in_category),
                        },
                    )
                top = await self._list_booking_services(category=None)
                if top:
                    return BookingOptionsOutput(
                        ready=False,
                        message=(
                            f"По названию «{service_name}» совпадений нет; по категории «{category}» в кэше тоже "
                            f"не нашлось услуг (сверь имя с sqns_list_categories и данные SQNS). "
                            f"Ниже до {len(top)} популярных услуг без фильтра по категории — выберите ближайшее или уточните запрос."
                        ),
                        alternatives={"services": self._services_to_booking_alternatives(top)},
                    )
            return BookingOptionsOutput(
                ready=False,
                message=(
                    f"Услуга '{service_name}' не найдена. Проверьте написание или синхронизируйте данные. "
                    f"Попробуйте использовать sqns_list_services для просмотра всех доступных услуг."
                ),
            )

        if len(services) == 1:
            service = services[0]
            resources_stmt = (
                select(SqnsResource)
                .join(
                    SqnsServiceResource,
                    SqnsServiceResource.resource_id == SqnsResource.id,
                )
                .where(
                    SqnsServiceResource.service_id == service.id,
                    SqnsResource.is_active == True,
                    SqnsResource.active == True,
                )
                .order_by(SqnsResource.name)
                .limit(BOOKING_OPTIONS_RESULT_LIMIT)
            )
            result = await self.db.execute(resources_stmt)
            resources = result.scalars().all()

            if not resources:
                return BookingOptionsOutput(
                    ready=False,
                    service_id=service.external_id,
                    service_name=service.name,
                    message=(
                        f"Для услуги '{service.name}' нет доступных специалистов. "
                        f"service_id={service.external_id} (используй это для sqns_list_slots, если найдешь специалиста)."
                    ),
                )

            alternatives = [
                BookingAlternative(
                    id=res.external_id,
                    name=res.name,
                    additional_info=res.information or res.specialization or "Специалист",
                )
                for res in resources
            ]

            return BookingOptionsOutput(
                ready=False,
                service_id=service.external_id,
                service_name=service.name,
                duration_seconds=service.duration_seconds,
                price=f"{service.price} руб." if service.price else None,
                message=(
                    f"Услугу '{service.name}' могут выполнить {len(resources)} специалистов. "
                    f"Выберите специалиста из списка alternatives.specialists. "
                    f"Используй поле 'id' из выбранного специалиста (это resource_id для sqns_list_slots). "
                    f"service_id={service.external_id} (используй это для sqns_list_slots)."
                ),
                alternatives={"specialists": alternatives},
            )

        service_ids = [s.id for s in services]
        join_stmt = (
            select(SqnsService, SqnsResource)
            .join(
                SqnsServiceResource,
                SqnsServiceResource.service_id == SqnsService.id,
            )
            .join(SqnsResource, SqnsServiceResource.resource_id == SqnsResource.id)
            .where(
                SqnsService.id.in_(service_ids),
                SqnsResource.is_active == True,
                SqnsResource.active == True,
            )
            .order_by(
                SqnsService.priority.desc(),
                SqnsService.name,
                SqnsResource.name,
            )
        )
        result = await self.db.execute(join_stmt)
        rows = result.all()
        specialists_by_service: dict[UUID, list[SqnsResource]] = {}
        for svc, res in rows:
            specialists_by_service.setdefault(svc.id, []).append(res)

        alternatives: list[BookingAlternative] = []
        for svc in services:
            spec_list = specialists_by_service.get(svc.id, [])
            cap = spec_list[:BOOKING_OPTIONS_RESULT_LIMIT]
            if cap:
                names = ", ".join(r.name for r in cap)
                if len(spec_list) > BOOKING_OPTIONS_RESULT_LIMIT:
                    names += f" (+{len(spec_list) - BOOKING_OPTIONS_RESULT_LIMIT} ещё)"
            else:
                names = "нет доступных специалистов"
            alternatives.append(
                BookingAlternative(
                    id=svc.external_id,
                    name=svc.name,
                    additional_info=(
                        f"{svc.duration_seconds // 60} мин • {names}"
                    ),
                )
            )

        return BookingOptionsOutput(
            ready=False,
            message=(
                f"По запросу «{service_name}» найдено {len(services)} услуг. "
                f"Уточните название или выберите одну услугу в alternatives.services "
                f"(в additional_info кратко перечислены врачи по связи услуга–специалист)."
            ),
            alternatives={"services": alternatives},
        )

    async def _validate_compatibility(
        self,
        service_name: str,
        specialist_name: str,
        *,
        category: str | None = None,
    ) -> BookingOptionsOutput:
        """Проверка совместимости: до N услуг и N врачей по ILIKE, пары только из M2M."""
        service_stmt = (
            select(SqnsService)
            .where(
                and_(
                    SqnsService.name.ilike(f"%{service_name}%"),
                    *self._booking_service_predicates(category=category),
                ),
            )
            .order_by(SqnsService.priority.desc(), SqnsService.name)
            .limit(BOOKING_OPTIONS_RESULT_LIMIT)
        )
        result = await self.db.execute(service_stmt)
        services = result.scalars().all()

        if not services:
            if category:
                in_category = await self._list_booking_services(category=category)
                if in_category:
                    return BookingOptionsOutput(
                        ready=False,
                        message=(
                            f"По названию «{service_name}» в категории «{category}» услуга не найдена "
                            f"(возможна неточность в названии). Указан специалист «{specialist_name}». "
                            f"Сначала выберите услугу из alternatives.services ({len(in_category)} вариантов в категории), "
                            f"затем вызовите sqns_find_booking_options с уточнённым service_name и тем же specialist_name."
                        ),
                        alternatives={
                            "services": self._services_to_booking_alternatives(in_category),
                        },
                    )
                top = await self._list_booking_services(category=None)
                if top:
                    return BookingOptionsOutput(
                        ready=False,
                        message=(
                            f"По названию «{service_name}» и категории «{category}» услуга не найдена; "
                            f"по категории в кэше пусто. Указан специалист «{specialist_name}». "
                            f"Ниже до {len(top)} популярных услуг без фильтра по категории — выберите услугу и повторите вызов с тем же specialist_name."
                        ),
                        alternatives={"services": self._services_to_booking_alternatives(top)},
                    )
            return BookingOptionsOutput(
                ready=False,
                message=(
                    f"Услуга '{service_name}' не найдена. "
                    f"Проверьте написание или используйте sqns_list_services для просмотра всех услуг."
                ),
            )

        resource_stmt = (
            select(SqnsResource)
            .where(
                SqnsResource.agent_id == self.agent_id,
                SqnsResource.is_active == True,
                SqnsResource.active == True,
                SqnsResource.name.ilike(f"%{specialist_name}%"),
            )
            .order_by(SqnsResource.name)
            .limit(BOOKING_OPTIONS_RESULT_LIMIT)
        )
        result = await self.db.execute(resource_stmt)
        resources = result.scalars().all()

        if not resources:
            if len(services) == 1:
                s0 = services[0]
                return BookingOptionsOutput(
                    ready=False,
                    service_id=s0.external_id,
                    service_name=s0.name,
                    message=(
                        f"Специалист '{specialist_name}' не найден. "
                        f"service_id={s0.external_id} (используй это для sqns_list_slots, если найдешь специалиста). "
                        f"Попробуйте использовать sqns_list_resources для просмотра всех специалистов."
                    ),
                )
            return BookingOptionsOutput(
                ready=False,
                message=(
                    f"Специалист '{specialist_name}' не найден. "
                    f"Попробуйте использовать sqns_list_resources для просмотра всех специалистов."
                ),
            )

        service_ids = [s.id for s in services]
        resource_ids = [r.id for r in resources]

        pairs_stmt = (
            select(SqnsService, SqnsResource, SqnsServiceResource)
            .join(
                SqnsServiceResource,
                SqnsServiceResource.service_id == SqnsService.id,
            )
            .join(
                SqnsResource,
                SqnsServiceResource.resource_id == SqnsResource.id,
            )
            .where(
                SqnsService.id.in_(service_ids),
                SqnsResource.id.in_(resource_ids),
                SqnsResource.is_active == True,
                SqnsResource.active == True,
            )
            .order_by(SqnsService.name, SqnsResource.name)
            .limit(BOOKING_OPTIONS_RESULT_LIMIT)
        )
        result = await self.db.execute(pairs_stmt)
        pair_rows = result.all()

        if len(pair_rows) == 1:
            service, resource, link = pair_rows[0]
            duration = link.duration_seconds or service.duration_seconds
            return BookingOptionsOutput(
                ready=True,
                service_id=service.external_id,
                service_name=service.name,
                resource_id=resource.external_id,
                resource_name=resource.name,
                duration_seconds=duration,
                price=f"{service.price} руб." if service.price else None,
                message=(
                    f"✓ Готово к записи: {resource.name} выполнит '{service.name}' ({duration // 60} мин). "
                    f"Используй service_id={service.external_id} и resource_id={resource.external_id} "
                    f"для вызова sqns_list_slots(resource_id={resource.external_id}, date='YYYY-MM-DD', service_ids=[{service.external_id}])."
                ),
            )

        if len(pair_rows) > 1:
            compatible_pairs = [
                BookingAlternative(
                    id=svc.external_id,
                    name=f"{svc.name} — {res.name}",
                    additional_info=(
                        f"service_id={svc.external_id} resource_id={res.external_id} "
                        f"для sqns_list_slots(resource_id={res.external_id}, service_ids=[{svc.external_id}])"
                    ),
                )
                for svc, res, _link in pair_rows
            ]
            return BookingOptionsOutput(
                ready=False,
                message=(
                    f"Найдено {len(compatible_pairs)} совместимых пар услуга–специалист по запросу. "
                    f"Выберите одну пару в alternatives.compatible_pairs (в additional_info оба id для SQNS)."
                ),
                alternatives={"compatible_pairs": compatible_pairs},
            )

        # 0 M2M-пар среди кандидатов
        s0, r0 = services[0], resources[0]
        other_specialists_stmt = (
            select(SqnsResource)
            .join(
                SqnsServiceResource,
                SqnsServiceResource.resource_id == SqnsResource.id,
            )
            .where(
                SqnsServiceResource.service_id == s0.id,
                SqnsResource.is_active == True,
                SqnsResource.active == True,
                SqnsResource.id.notin_(resource_ids),
            )
            .order_by(SqnsResource.name)
            .limit(BOOKING_OPTIONS_RESULT_LIMIT)
        )
        result = await self.db.execute(other_specialists_stmt)
        other_specialists = result.scalars().all()

        other_services_stmt = (
            select(SqnsService)
            .join(
                SqnsServiceResource,
                SqnsServiceResource.service_id == SqnsService.id,
            )
            .where(
                SqnsServiceResource.resource_id == r0.id,
                SqnsService.id.notin_(service_ids),
                and_(*self._booking_service_predicates(category=category)),
            )
            .order_by(SqnsService.priority.desc(), SqnsService.name)
            .limit(BOOKING_OPTIONS_RESULT_LIMIT)
        )
        result = await self.db.execute(other_services_stmt)
        other_services = result.scalars().all()

        alternatives: dict[str, list[BookingAlternative]] = {}
        if other_specialists:
            alternatives["other_specialists"] = [
                BookingAlternative(
                    id=res.external_id,
                    name=res.name,
                    additional_info=res.information or res.specialization or "Специалист",
                )
                for res in other_specialists
            ]
        if other_services:
            alternatives["other_services"] = [
                BookingAlternative(
                    id=svc.external_id,
                    name=svc.name,
                    additional_info=f"{svc.duration_seconds // 60} мин",
                )
                for svc in other_services
            ]

        root_service_id = services[0].external_id if len(services) == 1 else None
        root_service_name = services[0].name if len(services) == 1 else None
        root_resource_id = resources[0].external_id if len(resources) == 1 else None
        root_resource_name = resources[0].name if len(resources) == 1 else None

        return BookingOptionsOutput(
            ready=False,
            service_id=root_service_id,
            service_name=root_service_name,
            resource_id=root_resource_id,
            resource_name=root_resource_name,
            message=(
                f"Среди найденных по ILIKE услуг и специалистов нет совместимой пары в базе клиники "
                f"(ни один из кандидатов-врачей не назначен на кандидат-услугу). Уточните формулировку или "
                f"выберите другого специалиста / услугу из alternatives, если списки не пусты."
            ),
            alternatives=alternatives,
        )


async def sync_sqns_entities(
    db: AsyncSession,
    sqns_client: SQNSClient,
    agent_id: UUID,
    *,
    trigger: str,
) -> SyncResult:
    orchestrator = SqnsSyncOrchestrator(
        db=db,
        sqns_client=sqns_client,
        agent_id=agent_id,
        trigger=trigger,
    )
    return await orchestrator.sync()
