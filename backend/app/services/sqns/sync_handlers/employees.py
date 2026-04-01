from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsEmployee, SqnsResource
from app.services.sqns.client import SQNSClient
from app.services.sqns.sync_handlers.common import (
    compose_employee_name,
    parse_bool,
    parse_datetime,
    parse_int,
    unwrap_payload_list,
)

logger = structlog.get_logger(__name__)


async def mark_stale_sqns_resources(
    db: AsyncSession,
    agent_id: UUID,
    protected_external_ids: set[int],
    synced_at: datetime,
) -> int:
    """Помечает is_active=False тех sqns_resources, чьих external_id нет в protected_external_ids."""
    stmt = (
        update(SqnsResource)
        .where(
            SqnsResource.agent_id == agent_id,
            SqnsResource.is_active == True,
        )
        .values(
            is_active=False,
            synced_at=synced_at,
            updated_at=synced_at,
        )
    )
    if protected_external_ids:
        stmt = stmt.where(SqnsResource.external_id.notin_(protected_external_ids))
    result = await db.execute(stmt)
    return result.rowcount or 0


_EMPLOYEE_SERVICE_KEYS: tuple[str, ...] = (
    "services",
    "serviceIds",
    "service_ids",
    "linkedServices",
    "allowedServices",
    "employeeServices",
)


def _service_external_ids_from_employee(employee: dict[str, Any]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for key in _EMPLOYEE_SERVICE_KEYS:
        if key not in employee:
            continue
        raw = employee[key]
        if raw is None:
            continue
        seq = unwrap_payload_list(raw, extra_nested_keys=("services",))
        if seq is None:
            continue
        for item in seq:
            sid: int | None
            if isinstance(item, dict):
                sid = parse_int(
                    item.get("id")
                    or item.get("serviceId")
                    or item.get("service_id")
                )
            else:
                sid = parse_int(item)
            if sid is not None and sid not in seen:
                seen.add(sid)
                ordered.append(sid)
    return ordered


class SqnsEmployeesSyncHandler:
    def __init__(self, db: AsyncSession, client: SQNSClient, agent_id: UUID):
        self.db = db
        self.client = client
        self.agent_id = agent_id

    async def sync(self, *, modificate: int | None) -> dict[str, Any]:
        synced_at = datetime.now(timezone.utc)
        employees = await self.client.list_all_employees(
            per_page=100,
            modificate=modificate,
            is_fired=0,
            is_deleted=0,
        )
        employees_synced = 0
        resources_synced = 0
        active_external_ids: set[int] = set()
        employee_external_ids: set[int] = set()
        employee_service_links: list[tuple[int, int]] = []

        for employee in employees:
            if not isinstance(employee, dict):
                continue
            external_id = parse_int(employee.get("id"))
            if external_id is None:
                continue
            employee_external_ids.add(external_id)

            full_name = compose_employee_name(employee) or f"Employee {external_id}"
            is_fired = parse_bool(employee.get("isFired"), default=False)
            is_deleted = parse_bool(employee.get("isDeleted"), default=False)
            is_active = not is_fired and not is_deleted

            await self._upsert_employee(
                external_id=external_id,
                payload=employee,
                full_name=full_name,
                is_fired=is_fired,
                is_deleted=is_deleted,
                synced_at=synced_at,
            )
            employees_synced += 1

            await self._upsert_resource_projection(
                external_id=external_id,
                payload=employee,
                full_name=full_name,
                is_active=is_active,
                synced_at=synced_at,
            )
            resources_synced += 1
            if is_active:
                active_external_ids.add(external_id)

            for svc_ext in _service_external_ids_from_employee(employee):
                employee_service_links.append((external_id, svc_ext))

        resource_uuid_map = await self._load_active_resource_map()

        # Загружаем ПОЛНЫЙ список пар сотрудник→услуга из raw_data в БД,
        # а не из ответа API. Это гарантирует, что при инкрементальной синхронизации
        # (когда CRM возвращает только недавно изменённых сотрудников) у нас есть
        # полная картина: свежие данные для изменённых + сохранённые для остальных.
        # Без этого replace-стратегия в merge_employee_service_resource_links
        # удаляла бы связи неизменённых сотрудников.
        complete_employee_service_links = await self._load_employee_service_links_from_db()

        logger.info(
            "sqns_sync_employees_completed",
            agent_id=str(self.agent_id),
            employees_synced=employees_synced,
            resources_synced=resources_synced,
            employee_service_links_total=len(complete_employee_service_links),
            modificate=modificate,
        )
        return {
            "employees_synced": employees_synced,
            "resources_synced": resources_synced,
            "stale_resources": 0,
            "resource_uuid_map": resource_uuid_map,
            "employee_service_links": complete_employee_service_links,
            "employee_external_ids": employee_external_ids,
        }

    async def _upsert_employee(
        self,
        *,
        external_id: int,
        payload: dict[str, Any],
        full_name: str,
        is_fired: bool,
        is_deleted: bool,
        synced_at: datetime,
    ) -> None:
        stmt = insert(SqnsEmployee).values(
            id=uuid4(),
            agent_id=self.agent_id,
            external_id=external_id,
            firstname=str(payload.get("firstname")).strip() if payload.get("firstname") is not None else None,
            lastname=str(payload.get("lastname")).strip() if payload.get("lastname") is not None else None,
            patronymic=str(payload.get("patronymic")).strip() if payload.get("patronymic") is not None else None,
            full_name=full_name,
            image=str(payload.get("image")).strip() if payload.get("image") is not None else None,
            position=str(payload.get("position")).strip() if payload.get("position") is not None else None,
            rating=str(payload.get("rating")).strip() if payload.get("rating") is not None else None,
            updated_at_external=parse_datetime(payload.get("updateAt")),
            is_fired=is_fired,
            is_deleted=is_deleted,
            raw_data=payload,
            synced_at=synced_at,
            created_at=synced_at,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_sqns_employees_agent_external",
            set_={
                "firstname": stmt.excluded.firstname,
                "lastname": stmt.excluded.lastname,
                "patronymic": stmt.excluded.patronymic,
                "full_name": stmt.excluded.full_name,
                "image": stmt.excluded.image,
                "position": stmt.excluded.position,
                "rating": stmt.excluded.rating,
                "updated_at_external": stmt.excluded.updated_at_external,
                "is_fired": stmt.excluded.is_fired,
                "is_deleted": stmt.excluded.is_deleted,
                "raw_data": stmt.excluded.raw_data,
                "synced_at": stmt.excluded.synced_at,
                "updated_at": synced_at,
            },
        )
        await self.db.execute(stmt)

    async def _upsert_resource_projection(
        self,
        *,
        external_id: int,
        payload: dict[str, Any],
        full_name: str,
        is_active: bool,
        synced_at: datetime,
    ) -> None:
        specialization = (
            payload.get("position")
            or payload.get("specialization")
            or payload.get("specialty")
            or payload.get("role")
        )
        projection_payload = dict(payload)
        projection_payload["name"] = full_name
        projection_payload["specialization"] = specialization
        projection_payload["isActive"] = is_active

        stmt = insert(SqnsResource).values(
            id=uuid4(),
            agent_id=self.agent_id,
            external_id=external_id,
            name=full_name,
            specialization=str(specialization) if specialization else None,
            is_active=is_active,
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
        )
        await self.db.execute(stmt)

    async def _load_active_resource_map(self) -> dict[int, UUID]:
        stmt = select(SqnsResource.id, SqnsResource.external_id).where(
            SqnsResource.agent_id == self.agent_id,
            SqnsResource.is_active == True,
        )
        rows = (await self.db.execute(stmt)).all()
        return {int(external_id): resource_id for resource_id, external_id in rows}

    async def _load_employee_service_links_from_db(self) -> list[tuple[int, int]]:
        """
        Загружает пары (resource_external_id, service_external_id) из raw_data
        всех активных ресурсов в БД. Используется вместо ответа CRM API, чтобы
        всегда иметь полную картину при инкрементальной синхронизации.
        """
        stmt = select(SqnsResource.external_id, SqnsResource.raw_data).where(
            SqnsResource.agent_id == self.agent_id,
            SqnsResource.is_active == True,
        )
        rows = (await self.db.execute(stmt)).all()
        links: list[tuple[int, int]] = []
        for ext_id, raw_data in rows:
            if not isinstance(raw_data, dict):
                continue
            for svc_ext in _service_external_ids_from_employee(raw_data):
                links.append((int(ext_id), svc_ext))
        return links
