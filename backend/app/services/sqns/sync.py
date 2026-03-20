"""Service for synchronizing SQNS data to local database cache."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import re
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, select, func, update
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
from app.services.sqns.sync_orchestrator import SqnsSyncOrchestrator

logger = structlog.get_logger(__name__)


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

            # 2. Upsert resources (specialists)
            synced_resource_external_ids: set[int] = set()
            for external_id, resource_data in resources_map.items():
                await self._upsert_resource(external_id, resource_data, synced_at)
                synced_resource_external_ids.add(external_id)
                resources_count += 1

            stale_resources_count = await self._mark_stale_resources_inactive(
                synced_resource_external_ids,
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

                # Upsert service
                service_uuid = await self._upsert_service(external_id, service, synced_at)
                services_count += 1

                # Sync M2M links for this service
                resource_links = service.get("resources", [])
                if isinstance(resource_links, list):
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
        4. Ничего → топ-20 услуг по priority
        """
        service_name = input_data.service_name
        specialist_name = input_data.specialist_name

        # Сценарий 4: Ничего не указано → топ услуг
        if not service_name and not specialist_name:
            return await self._get_top_services()

        # Сценарий 2: Только специалист → услуги специалиста
        if specialist_name and not service_name:
            return await self._find_services_by_specialist(specialist_name)

        # Сценарий 1: Только услуга → специалисты для услуги
        if service_name and not specialist_name:
            return await self._find_specialists_by_service(service_name)

        # Сценарий 3: Оба параметра → проверка совместимости
        return await self._validate_compatibility(service_name, specialist_name)

    async def _get_top_services(self) -> BookingOptionsOutput:
        """Возвращает топ-20 услуг по приоритету."""
        stmt = (
            select(SqnsService)
            .where(
                SqnsService.agent_id == self.agent_id,
                SqnsService.is_enabled == True,
            )
            .order_by(SqnsService.priority.desc(), SqnsService.name)
            .limit(20)
        )
        result = await self.db.execute(stmt)
        services = result.scalars().all()

        if not services:
            return BookingOptionsOutput(
                ready=False,
                message="Нет доступных услуг. Пожалуйста, синхронизируйте данные из SQNS.",
            )

        alternatives = [
            BookingAlternative(
                id=svc.external_id,
                name=svc.name,
                additional_info=f"{svc.category or 'Без категории'} • {svc.duration_seconds // 60} мин",
            )
            for svc in services
        ]

        return BookingOptionsOutput(
            ready=False,
            message=f"Доступно {len(services)} услуг. Выберите услугу или специалиста для продолжения.",
            alternatives={"services": alternatives},
        )

    async def _find_services_by_specialist(
        self,
        specialist_name: str,
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
                SqnsService.is_enabled == True,
            )
            .order_by(SqnsService.priority.desc(), SqnsService.name)
            .limit(20)
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
    ) -> BookingOptionsOutput:
        """Поиск специалистов, которые могут выполнять услугу."""
        # Поиск услуги по названию (ILIKE)
        service_stmt = (
            select(SqnsService)
            .where(
                SqnsService.agent_id == self.agent_id,
                SqnsService.is_enabled == True,
                SqnsService.name.ilike(f"%{service_name}%"),
            )
            .limit(1)
        )
        result = await self.db.execute(service_stmt)
        service = result.scalar_one_or_none()

        if not service:
            return BookingOptionsOutput(
                ready=False,
                message=(
                    f"Услуга '{service_name}' не найдена. Проверьте написание или синхронизируйте данные. "
                    f"Попробуйте использовать sqns_list_services для просмотра всех доступных услуг."
                ),
            )

        # Найти специалистов для этой услуги
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
            .limit(20)
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

    async def _validate_compatibility(
        self,
        service_name: str,
        specialist_name: str,
    ) -> BookingOptionsOutput:
        """Проверка совместимости услуги и специалиста."""
        # Найти услугу
        service_stmt = (
            select(SqnsService)
            .where(
                SqnsService.agent_id == self.agent_id,
                SqnsService.is_enabled == True,
                SqnsService.name.ilike(f"%{service_name}%"),
            )
            .limit(1)
        )
        result = await self.db.execute(service_stmt)
        service = result.scalar_one_or_none()

        if not service:
            return BookingOptionsOutput(
                ready=False,
                message=(
                    f"Услуга '{service_name}' не найдена. "
                    f"Проверьте написание или используйте sqns_list_services для просмотра всех услуг."
                ),
            )

        # Найти специалиста
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
                service_id=service.external_id,
                service_name=service.name,
                message=(
                    f"Специалист '{specialist_name}' не найден. "
                    f"service_id={service.external_id} (используй это для sqns_list_slots, если найдешь специалиста). "
                    f"Попробуйте использовать sqns_list_resources для просмотра всех специалистов."
                ),
            )

        # Проверить связь
        link_stmt = select(SqnsServiceResource).where(
            SqnsServiceResource.service_id == service.id,
            SqnsServiceResource.resource_id == resource.id,
        )
        result = await self.db.execute(link_stmt)
        link = result.scalar_one_or_none()

        if link:
            # Совместимы! Возвращаем ID для записи
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

        # Несовместимы! Предложить альтернативы
        # Найти других специалистов для этой услуги
        other_specialists_stmt = (
            select(SqnsResource)
            .join(
                SqnsServiceResource,
                SqnsServiceResource.resource_id == SqnsResource.id,
            )
            .where(
                SqnsServiceResource.service_id == service.id,
                SqnsResource.is_active == True,
                SqnsResource.active == True,
                SqnsResource.id != resource.id,
            )
            .limit(5)
        )
        result = await self.db.execute(other_specialists_stmt)
        other_specialists = result.scalars().all()

        # Найти другие услуги этого специалиста
        other_services_stmt = (
            select(SqnsService)
            .join(
                SqnsServiceResource,
                SqnsServiceResource.service_id == SqnsService.id,
            )
            .where(
                SqnsServiceResource.resource_id == resource.id,
                SqnsService.is_enabled == True,
                SqnsService.id != service.id,
            )
            .limit(5)
        )
        result = await self.db.execute(other_services_stmt)
        other_services = result.scalars().all()

        alternatives = {}
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

        return BookingOptionsOutput(
            ready=False,
            service_id=service.external_id,
            service_name=service.name,
            resource_id=resource.external_id,
            resource_name=resource.name,
            message=(
                f"✗ {resource.name} не может выполнить '{service.name}'. "
                f"Выберите другого специалиста или другую услугу из alternatives. "
                f"Используй поле 'id' из выбранного элемента (это external_id для SQNS API)."
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
