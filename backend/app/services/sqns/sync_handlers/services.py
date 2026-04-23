from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import re
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import (
    SqnsResource,
    SqnsService,
    SqnsServiceCategory,
    SqnsServiceResource,
)
from app.services.sqns.client import SQNSClient, SQNSClientError
from app.services.sqns.sync_handlers.common import coerce_number, parse_int, unwrap_payload_list
from app.services.sqns.sync_handlers.employees import mark_stale_sqns_resources

logger = structlog.get_logger(__name__)


def _resource_external_id_from_link_item(item: Any) -> int | None:
    if isinstance(item, dict):
        return parse_int(
            item.get("id")
            or item.get("resourceId")
            or item.get("resource_id")
            or item.get("employeeId")
            or item.get("employee_id")
        )
    return parse_int(item)


def _normalize_resource_link_rows(raw_items: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in raw_items:
        rid = _resource_external_id_from_link_item(item)
        if rid is None:
            continue
        if isinstance(item, dict):
            row = dict(item)
            row["id"] = rid
            rows.append(row)
        else:
            rows.append({"id": rid})
    return rows


def collect_service_resource_links(service: dict[str, Any]) -> list[dict[str, Any]] | None:
    """
    Поле resources[] в ответах GET /api/v2/booking/service и GET /api/v2/booking/service/{id}
    (док. SQNS CrmExchangeApi, раздел «Онлайн запись»). Выгрузка GET /api/v2/service этого поля не содержит.

    None — ключа resources нет или список нельзя разобрать: не меняем связи в кэше.
    Непустой список — заменить связи. Пустой массив resources в payload считаем осмысленным «нет привязок».
    """
    if "resources" not in service:
        return None
    raw = service["resources"]
    if raw is None:
        return None
    seq = unwrap_payload_list(raw)
    if seq is None:
        return None
    return _normalize_resource_link_rows(seq)


async def load_booking_resources_by_service_external_id(
    client: SQNSClient,
) -> dict[int, list[dict[str, Any]]]:
    """Индекс service.id → resources[] из GET /api/v2/booking/service."""
    try:
        items = await client.list_all_booking_services(per_page=100)
    except SQNSClientError as exc:
        logger.warning("sqns_booking_services_unavailable", error=str(exc))
        return {}
    out: dict[int, list[dict[str, Any]]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        sid = parse_int(item.get("id"))
        if sid is None:
            continue
        res = item.get("resources")
        if isinstance(res, list) and res:
            out[sid] = res
    return out


async def merge_service_payload_from_booking_api(
    client: SQNSClient,
    service: dict[str, Any],
    external_id_int: int,
    booking_resources_by_id: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Дополняет объект услуги из /api/v2/service данными booking API (resources)."""
    br = booking_resources_by_id.get(external_id_int)
    if br is not None:
        service = {**service, "resources": list(br)}
    if collect_service_resource_links(service) is not None:
        return service
    detail = await client.get_booking_service_detail(external_id_int)
    if isinstance(detail, dict) and detail:
        return {**service, **detail}
    return service


def resource_data_from_service_link(external_id: int, link: dict[str, Any]) -> dict[str, Any]:
    """Минимальный payload для sqns_resources, если специалист есть в услуге (booking), но не в /employee."""
    name = (
        link.get("name")
        or link.get("fullName")
        or link.get("title")
        or link.get("fio")
        or link.get("displayName")
    )
    spec = (
        link.get("specialization")
        or link.get("specialty")
        or link.get("position")
    )
    merged = dict(link)
    merged["name"] = str(name).strip() if name else f"Специалист {external_id}"
    if spec:
        merged["specialization"] = spec
    merged["isActive"] = True
    return merged


async def collect_resource_refs_from_services_payload(
    client: SQNSClient,
    services_data: list[Any],
    booking_resources_by_id: dict[int, list[dict[str, Any]]],
) -> tuple[set[int], dict[int, dict[str, Any]]]:
    """
    Все external_id специалистов из resources[] услуг (после merge с booking API).
    Нужны, чтобы не помечать их устаревшими, если SQNS не вернул их в list_all_employees.
    """
    external_ids: set[int] = set()
    first_link_by_id: dict[int, dict[str, Any]] = {}
    for service in services_data:
        if not isinstance(service, dict) or "id" not in service:
            continue
        try:
            ext_svc = int(service["id"])
        except (TypeError, ValueError):
            continue
        merged = await merge_service_payload_from_booking_api(
            client,
            service,
            ext_svc,
            booking_resources_by_id,
        )
        links = collect_service_resource_links(merged)
        if not links:
            continue
        for link in links:
            if not isinstance(link, dict) or "id" not in link:
                continue
            try:
                rid = int(link["id"])
            except (TypeError, ValueError):
                continue
            external_ids.add(rid)
            if rid not in first_link_by_id:
                first_link_by_id[rid] = link
    return external_ids, first_link_by_id


class SqnsServicesSyncHandler:
    def __init__(self, db: AsyncSession, client: SQNSClient, agent_id: UUID):
        self.db = db
        self.client = client
        self.agent_id = agent_id

    @classmethod
    def _parse_price(cls, value: Any) -> Decimal | None:
        parsed = coerce_number(value)
        if parsed is None:
            return None
        return Decimal(str(parsed))

    @classmethod
    def _parse_duration_seconds(cls, value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, dict):
            unit = value.get("unit") or value.get("units")
            if unit:
                unit_label = str(unit).lower()
                number = coerce_number(
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
                number = coerce_number(value.get("durationMinutes") or value.get("minutes"))
                if number is not None:
                    return int(number * 60)
            if "durationHours" in value or "hours" in value:
                number = coerce_number(value.get("durationHours") or value.get("hours"))
                if number is not None:
                    return int(number * 3600)

        number = coerce_number(value)
        if number is None:
            return 0
        return int(number)

    async def _upsert_resource_from_booking_link(
        self,
        external_id: int,
        link: dict[str, Any],
        synced_at: datetime,
    ) -> UUID:
        """Специалист из онлайн-записи, которого нет в ответе /employee — минимальная проекция в sqns_resources."""
        projection_payload = resource_data_from_service_link(external_id, link)
        full_name = projection_payload["name"]
        specialization = (
            projection_payload.get("specialization")
            or projection_payload.get("specialty")
            or projection_payload.get("position")
        )
        stmt = insert(SqnsResource).values(
            id=uuid4(),
            agent_id=self.agent_id,
            external_id=external_id,
            name=full_name,
            specialization=str(specialization) if specialization else None,
            is_active=True,
            active=True,
            information=None,
            raw_data=projection_payload,
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

    async def sync(
        self,
        *,
        modificate: int | None,
        resource_uuid_map: dict[int, UUID],
        employee_service_links: list[tuple[int, int]] | None = None,
        employee_external_ids: set[int] | None = None,
        employee_full_sync: bool = True,
    ) -> dict[str, int]:
        synced_at = datetime.now(timezone.utc)
        services_data = await self.client.list_all_services(per_page=100, modificate=modificate)
        booking_resources_by_id = await load_booking_resources_by_service_external_id(self.client)
        resource_ids_from_services, link_by_resource_id = await collect_resource_refs_from_services_payload(
            self.client,
            services_data,
            booking_resources_by_id,
        )
        emp_ids = employee_external_ids or set()
        for ext_res in resource_ids_from_services:
            if ext_res in resource_uuid_map:
                continue
            link = link_by_resource_id.get(ext_res, {})
            resource_uuid = await self._upsert_resource_from_booking_link(ext_res, link, synced_at)
            resource_uuid_map[ext_res] = resource_uuid
            logger.info(
                "sqns_resource_upserted_from_service_link",
                agent_id=str(self.agent_id),
                external_id=ext_res,
            )

        services_synced = 0
        links_synced = 0
        categories_touched: set[str] = set()
        services_with_authoritative_links: set[int] = set()
        synced_service_external_ids: set[int] = set()

        for service in services_data:
            if not isinstance(service, dict):
                continue
            external_id = service.get("id")
            try:
                external_id_int = int(external_id)
            except (TypeError, ValueError):
                continue

            service = await merge_service_payload_from_booking_api(
                self.client,
                service,
                external_id_int,
                booking_resources_by_id,
            )

            service_uuid = await self._upsert_service(external_id_int, service, synced_at)
            services_synced += 1
            synced_service_external_ids.add(external_id_int)

            resource_links = collect_service_resource_links(service)
            if resource_links is not None:
                services_with_authoritative_links.add(external_id_int)
                links_synced += await self._sync_service_resources(
                    service_uuid=service_uuid,
                    resource_links=resource_links,
                    resource_uuid_map=resource_uuid_map,
                    synced_at=synced_at,
                )

            category_name = service.get("category") or service.get("categoryName")
            if isinstance(category_name, dict):
                category_name = (
                    category_name.get("name")
                    or category_name.get("title")
                    or category_name.get("label")
                    or category_name.get("value")
                )
            if isinstance(category_name, str):
                normalized = category_name.strip()
                if normalized:
                    categories_touched.add(normalized)

        for category_name in categories_touched:
            await self._upsert_category(category_name, synced_at)
        # Мягкое удаление категорий только при полной синхронизации.
        # При инкрементальной services_data содержит лишь недавно изменённые услуги,
        # поэтому categories_touched неполный — prune пометил бы валидные как удалённые.
        stale_categories = (
            await self._soft_delete_stale_categories(categories_touched, synced_at)
            if modificate is None
            else 0
        )

        # Помечаем услуги как stale только при полной синхронизации.
        # Физически не удаляем, чтобы сохранить локальные is_enabled/priority
        # на случай возврата услуги во внешней системе.
        stale_services = (
            await self._mark_stale_services(synced_service_external_ids, synced_at)
            if modificate is None
            else 0
        )

        augment = await self.merge_employee_service_resource_links(
            employee_service_links or [],
            resource_uuid_map,
            synced_at,
            services_with_authoritative_links=services_with_authoritative_links,
            full_sync=employee_full_sync,
        )
        links_synced += augment

        stale_resources = 0
        if modificate is None:
            protected_ids = emp_ids | resource_ids_from_services
            stale_resources = await mark_stale_sqns_resources(
                self.db,
                self.agent_id,
                protected_ids,
                synced_at,
            )

        total_categories_stmt = select(func.count(SqnsServiceCategory.id)).where(
            SqnsServiceCategory.agent_id == self.agent_id
        )
        categories_total = int((await self.db.execute(total_categories_stmt)).scalar() or 0)

        logger.info(
            "sqns_sync_services_completed",
            agent_id=str(self.agent_id),
            services_synced=services_synced,
            categories_synced=categories_total,
            links_synced=links_synced,
            links_merged_from_employees=augment,
            stale_resources=stale_resources,
            stale_categories=stale_categories,
            stale_services=stale_services,
            modificate=modificate,
        )
        return {
            "services_synced": services_synced,
            "categories_synced": categories_total,
            "links_synced": links_synced,
            "stale_resources": stale_resources,
            "stale_categories": stale_categories,
            "stale_services": stale_services,
        }

    async def _upsert_service(
        self,
        external_id: int,
        service_data: dict[str, Any],
        synced_at: datetime,
    ) -> UUID:
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
            is_enabled=True,
            priority=0,
            raw_data=service_data,
            synced_at=synced_at,
            stale_since=None,
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
                # Услуга снова пришла из SQNS — снимаем флаг stale, сохраняя
                # локальные is_enabled/priority.
                "stale_since": None,
                "updated_at": synced_at,
            },
        ).returning(SqnsService.id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _sync_service_resources(
        self,
        *,
        service_uuid: UUID,
        resource_links: list[dict[str, Any]],
        resource_uuid_map: dict[int, UUID],
        synced_at: datetime,
    ) -> int:
        await self.db.execute(
            delete(SqnsServiceResource).where(
                SqnsServiceResource.service_id == service_uuid
            )
        )

        links_to_insert: list[dict[str, Any]] = []
        for link in resource_links:
            if not isinstance(link, dict) or "id" not in link:
                continue
            try:
                resource_external_id = int(link["id"])
            except (TypeError, ValueError):
                continue
            resource_uuid = resource_uuid_map.get(resource_external_id)
            if not resource_uuid:
                continue

            duration_override = self._parse_duration_seconds(
                link.get("durationSeconds") or link.get("duration") or link.get("durationMinutes")
            )
            links_to_insert.append(
                {
                    "id": uuid4(),
                    "service_id": service_uuid,
                    "resource_id": resource_uuid,
                    "duration_seconds": duration_override if duration_override else None,
                    "created_at": synced_at,
                }
            )

        if links_to_insert:
            await self.db.execute(insert(SqnsServiceResource), links_to_insert)
        return len(links_to_insert)

    async def merge_employee_service_resource_links(
        self,
        pairs: list[tuple[int, int]],
        resource_uuid_map: dict[int, UUID],
        synced_at: datetime,
        *,
        services_with_authoritative_links: set[int] | None = None,
        full_sync: bool = True,
    ) -> int:
        """
        Синхронизирует связи из карточек сотрудников как fallback-источник:
        - для услуг с authoritative resources[] (booking API) ничего не трогаем;
        - full_sync=True  → replace: удалить старые связи, вставить новые (полная синхронизация);
        - full_sync=False → add-only: только добавить отсутствующие связи (инкрементальная синхронизация).
          При инкрементальной синхронизации employee_service_links содержит только недавно изменённых
          сотрудников, поэтому replace удалил бы связи других сотрудников с теми же услугами.
        """
        svc_rows = (
            await self.db.execute(
                select(SqnsService.id, SqnsService.external_id).where(
                    SqnsService.agent_id == self.agent_id
                )
            )
        ).all()
        service_by_ext = {int(ext): sid for sid, ext in svc_rows}
        authoritative_services = services_with_authoritative_links or set()
        fallback_service_ext_ids = set(service_by_ext.keys()) - authoritative_services
        touched_fallback_services: set[int] = set()
        desired_by_service: dict[UUID, set[UUID]] = {}

        for resource_ext, service_ext in pairs:
            if service_ext in authoritative_services:
                continue
            if service_ext not in fallback_service_ext_ids:
                continue
            touched_fallback_services.add(service_ext)
            resource_uuid = resource_uuid_map.get(resource_ext)
            service_uuid = service_by_ext.get(service_ext)
            if resource_uuid is None or service_uuid is None:
                continue
            desired_by_service.setdefault(service_uuid, set()).add(resource_uuid)

        if not touched_fallback_services:
            return 0

        touched_service_uuids = [
            service_by_ext[svc_ext]
            for svc_ext in touched_fallback_services
            if svc_ext in service_by_ext
        ]
        if not touched_service_uuids:
            return 0

        if full_sync:
            # Replace: удаляем все существующие связи для затронутых услуг, затем вставляем полный набор.
            # Корректно только при полной синхронизации, когда pairs содержит ВСЕ пары всех сотрудников.
            await self.db.execute(
                delete(SqnsServiceResource).where(
                    SqnsServiceResource.service_id.in_(touched_service_uuids)
                )
            )

        rows_to_insert: list[dict[str, Any]] = []
        for service_uuid, resource_ids in desired_by_service.items():
            for resource_uuid in resource_ids:
                rows_to_insert.append(
                    {
                        "id": uuid4(),
                        "service_id": service_uuid,
                        "resource_id": resource_uuid,
                        "duration_seconds": None,
                        "created_at": synced_at,
                    }
                )

        if not rows_to_insert:
            return 0

        if full_sync:
            await self.db.execute(insert(SqnsServiceResource), rows_to_insert)
        else:
            # Add-only: вставляем только отсутствующие связи, существующие не трогаем.
            stmt = insert(SqnsServiceResource).on_conflict_do_nothing(
                constraint="uq_sqns_service_resources"
            )
            await self.db.execute(stmt, rows_to_insert)

        return len(rows_to_insert)

    async def _upsert_category(self, category_name: str, synced_at: datetime) -> None:
        normalized_name = re.sub(r"\s+", " ", category_name).strip()
        if not normalized_name:
            return
        stmt = insert(SqnsServiceCategory).values(
            id=uuid4(),
            agent_id=self.agent_id,
            name=normalized_name,
            is_enabled=True,
            priority=0,
            deleted_at=None,
            created_at=synced_at,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_sqns_categories_agent_name",
            set_={
                # Категория снова пришла из SQNS — снимаем мягкое удаление,
                # сохраняя локальные is_enabled/priority.
                "deleted_at": None,
                "updated_at": synced_at,
            },
        )
        await self.db.execute(stmt)

    async def _soft_delete_stale_categories(
        self,
        active_names: set[str],
        synced_at: datetime,
    ) -> int:
        """
        Мягкое удаление категорий, исчезнувших из SQNS.

        Физически не удаляем: сохраняем is_enabled/priority, выставленные
        пользователем, на случай возврата категории (например, переименования
        с последующим откатом или временного скрытия во внешней системе).
        """
        stmt = (
            update(SqnsServiceCategory)
            .where(
                SqnsServiceCategory.agent_id == self.agent_id,
                SqnsServiceCategory.deleted_at.is_(None),
            )
            .values(deleted_at=synced_at, updated_at=synced_at)
        )
        if active_names:
            stmt = stmt.where(SqnsServiceCategory.name.notin_(active_names))
        result = await self.db.execute(stmt)
        return int(result.rowcount or 0)

    async def _mark_stale_services(
        self,
        active_external_ids: set[int],
        synced_at: datetime,
    ) -> int:
        """
        Помечает услуги, отсутствующие во внешнем ответе, как stale.

        Физически не удаляем — локальные настройки (is_enabled, priority)
        должны пережить возможный возврат услуги. Повторный upsert сбросит
        stale_since обратно в NULL.
        """
        stmt = (
            update(SqnsService)
            .where(
                SqnsService.agent_id == self.agent_id,
                SqnsService.stale_since.is_(None),
            )
            .values(stale_since=synced_at, updated_at=synced_at)
        )
        if active_external_ids:
            stmt = stmt.where(SqnsService.external_id.notin_(active_external_ids))
        result = await self.db.execute(stmt)
        return int(result.rowcount or 0)
