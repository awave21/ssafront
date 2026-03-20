from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import re
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsService, SqnsServiceCategory, SqnsServiceResource
from app.services.sqns.client import SQNSClient
from app.services.sqns.sync_handlers.common import coerce_number

logger = structlog.get_logger(__name__)


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

    async def sync(
        self,
        *,
        modificate: int | None,
        resource_uuid_map: dict[int, UUID],
    ) -> dict[str, int]:
        synced_at = datetime.now(timezone.utc)
        services_data = await self.client.list_all_services(per_page=100, modificate=modificate)
        services_synced = 0
        links_synced = 0
        categories_touched: set[str] = set()

        for service in services_data:
            if not isinstance(service, dict):
                continue
            external_id = service.get("id")
            try:
                external_id_int = int(external_id)
            except (TypeError, ValueError):
                continue

            service_uuid = await self._upsert_service(external_id_int, service, synced_at)
            services_synced += 1

            resource_links = service.get("resources")
            if isinstance(resource_links, list):
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
            modificate=modificate,
        )
        return {
            "services_synced": services_synced,
            "categories_synced": categories_total,
            "links_synced": links_synced,
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
            created_at=synced_at,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_sqns_categories_agent_name",
            set_={"updated_at": synced_at},
        )
        await self.db.execute(stmt)
