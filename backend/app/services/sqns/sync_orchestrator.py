from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.sqns_service import SqnsSyncRun
from app.schemas.sqns_service import SyncResult
from app.services.sqns.client import SQNSClient
from app.services.sqns.sync_cursor import SqnsSyncCursorStore
from app.services.sqns.sync_handlers import (
    SqnsClientsSyncHandler,
    SqnsCommoditiesSyncHandler,
    SqnsEmployeesSyncHandler,
    SqnsPaymentsSyncHandler,
    SqnsServicesSyncHandler,
    SqnsVisitsSyncHandler,
)

logger = structlog.get_logger(__name__)
_VISITS_HISTORY_STATE_KEY = "history_backfill"
_VISITS_HISTORY_START_DATE = date(1970, 1, 1)
_VISITS_HISTORY_CHUNK_DAYS = 90
_VISITS_RECENT_WINDOW_SYNC_STATE_KEY = "recent_window_resynced"


class SqnsSyncOrchestrator:
    def __init__(
        self,
        db: AsyncSession,
        sqns_client: SQNSClient,
        agent_id: UUID,
        *,
        trigger: str = "manual",
    ):
        self.db = db
        self.sqns_client = sqns_client
        self.agent_id = agent_id
        self.trigger = trigger
        self.cursor_store = SqnsSyncCursorStore(db, agent_id)

    async def sync(self) -> SyncResult:
        started_at = datetime.now(timezone.utc)
        run_id = await self._start_run(started_at)
        counters: dict[str, int] = {
            "resources_synced": 0,
            "services_synced": 0,
            "categories_synced": 0,
            "links_synced": 0,
            "employees_synced": 0,
            "clients_synced": 0,
            "commodities_synced": 0,
            "visits_synced": 0,
            "payments_synced": 0,
        }

        try:
            employees_handler = SqnsEmployeesSyncHandler(self.db, self.sqns_client, self.agent_id)
            clients_handler = SqnsClientsSyncHandler(self.db, self.sqns_client, self.agent_id)
            services_handler = SqnsServicesSyncHandler(self.db, self.sqns_client, self.agent_id)
            commodities_handler = SqnsCommoditiesSyncHandler(self.db, self.sqns_client, self.agent_id)
            visits_handler = SqnsVisitsSyncHandler(self.db, self.sqns_client, self.agent_id)
            payments_handler = SqnsPaymentsSyncHandler(self.db, self.sqns_client, self.agent_id)

            employees_modificate = await self.cursor_store.get_modificate("employees")
            employees_result = await employees_handler.sync(modificate=employees_modificate)
            counters["employees_synced"] = int(employees_result.get("employees_synced", 0))
            counters["resources_synced"] = int(employees_result.get("resources_synced", 0))
            resource_uuid_map = employees_result.get("resource_uuid_map", {})
            await self.cursor_store.upsert(
                entity="employees",
                modificate_value=int(started_at.timestamp()),
                last_success_at=started_at,
            )
            await self.db.commit()

            clients_modificate = await self.cursor_store.get_modificate("clients")
            clients_result = await clients_handler.sync(modificate=clients_modificate)
            counters["clients_synced"] = int(clients_result.get("clients_synced", 0))
            await self.cursor_store.upsert(
                entity="clients",
                modificate_value=int(started_at.timestamp()),
                last_success_at=started_at,
            )
            await self.db.commit()

            services_modificate = await self.cursor_store.get_modificate("services")
            services_result = await services_handler.sync(
                modificate=services_modificate,
                resource_uuid_map=resource_uuid_map,
                employee_service_links=employees_result.get("employee_service_links") or [],
            )
            counters["services_synced"] = int(services_result.get("services_synced", 0))
            counters["categories_synced"] = int(services_result.get("categories_synced", 0))
            counters["links_synced"] = int(services_result.get("links_synced", 0))
            await self.cursor_store.upsert(
                entity="services",
                modificate_value=int(started_at.timestamp()),
                last_success_at=started_at,
            )
            await self.db.commit()

            commodities_modificate = await self.cursor_store.get_modificate("commodities")
            commodities_result = await commodities_handler.sync(modificate=commodities_modificate)
            counters["commodities_synced"] = int(commodities_result.get("commodities_synced", 0))
            await self.cursor_store.upsert(
                entity="commodities",
                modificate_value=int(started_at.timestamp()),
                last_success_at=started_at,
            )
            await self.db.commit()

            visits_cursor = await self.cursor_store.get("visits")
            visits_cursor_state = visits_cursor.state if visits_cursor is not None and isinstance(visits_cursor.state, dict) else {}
            visits_modificate = visits_cursor.modificate_value if visits_cursor is not None else None
            visits_date_from, visits_date_till = self._resolve_visits_incremental_range()
            # После релизов с изменением парсинга визитов делаем один полный ресинк текущего окна,
            # чтобы обновить ранее сохраненные записи, которые могли не попадать в modificate-режим.
            force_recent_window_resync = not bool(visits_cursor_state.get(_VISITS_RECENT_WINDOW_SYNC_STATE_KEY))
            visits_result = await visits_handler.sync(
                date_from=visits_date_from.isoformat(),
                date_till=visits_date_till.isoformat(),
                modificate=None if force_recent_window_resync else visits_modificate,
            )
            visits_backfill_synced, visits_state = await self._sync_visits_history_backfill(
                visits_handler=visits_handler,
                visits_cursor_state=visits_cursor_state,
                recent_date_from=visits_date_from,
            )
            visits_state[_VISITS_RECENT_WINDOW_SYNC_STATE_KEY] = True
            counters["visits_synced"] = int(visits_result.get("visits_synced", 0)) + visits_backfill_synced
            await self.cursor_store.upsert(
                entity="visits",
                modificate_value=int(started_at.timestamp()),
                date_from=visits_date_from,
                date_till=visits_date_till,
                last_success_at=started_at,
                state=visits_state,
            )
            await self.db.commit()

            payments_date_from, payments_date_to = self._resolve_payments_range()
            payments_result = await payments_handler.sync(
                date_from=payments_date_from.isoformat(),
                date_to=payments_date_to.isoformat(),
            )
            counters["payments_synced"] = int(payments_result.get("payments_synced", 0))
            await self.cursor_store.upsert(
                entity="payments",
                date_from=payments_date_from,
                date_till=payments_date_to,
                last_success_at=started_at,
                state={"window_days": get_settings().sqns_sync_payments_window_days},
            )
            await self.db.commit()

            synced_at = datetime.now(timezone.utc)
            await self._finish_run(
                run_id=run_id,
                status="success",
                started_at=started_at,
                entities=counters,
                details={"trigger": self.trigger},
                error=None,
            )
            message = (
                f"Синхронизировано: услуги={counters['services_synced']}, специалисты={counters['resources_synced']}, "
                f"сотрудники={counters['employees_synced']}, клиенты={counters['clients_synced']}, "
                f"товары={counters['commodities_synced']}, "
                f"визиты={counters['visits_synced']}, платежи={counters['payments_synced']}"
            )
            return SyncResult(
                success=True,
                message=message,
                resources_synced=counters["resources_synced"],
                services_synced=counters["services_synced"],
                categories_synced=counters["categories_synced"],
                links_synced=counters["links_synced"],
                employees_synced=counters["employees_synced"],
                clients_synced=counters["clients_synced"],
                commodities_synced=counters["commodities_synced"],
                visits_synced=counters["visits_synced"],
                payments_synced=counters["payments_synced"],
                synced_at=synced_at,
            )

        except Exception as exc:
            await self.db.rollback()
            error_message = str(exc)
            await self._finish_run(
                run_id=run_id,
                status="failed",
                started_at=started_at,
                entities=counters,
                details={"trigger": self.trigger},
                error=error_message,
            )
            logger.exception(
                "sqns_sync_orchestrator_failed",
                agent_id=str(self.agent_id),
                trigger=self.trigger,
                error=error_message,
            )
            return SyncResult(
                success=False,
                message=f"Ошибка синхронизации: {error_message}",
                errors=[error_message],
                resources_synced=counters["resources_synced"],
                services_synced=counters["services_synced"],
                categories_synced=counters["categories_synced"],
                links_synced=counters["links_synced"],
                employees_synced=counters["employees_synced"],
                clients_synced=counters["clients_synced"],
                commodities_synced=counters["commodities_synced"],
                visits_synced=counters["visits_synced"],
                payments_synced=counters["payments_synced"],
            )

    async def _start_run(self, started_at: datetime) -> UUID:
        run_id = uuid4()
        run = SqnsSyncRun(
            id=run_id,
            agent_id=self.agent_id,
            trigger=self.trigger,
            status="running",
            started_at=started_at,
            created_at=started_at,
            details={"trigger": self.trigger},
        )
        self.db.add(run)
        await self.db.commit()
        return run_id

    async def _finish_run(
        self,
        *,
        run_id: UUID,
        status: str,
        started_at: datetime,
        entities: dict[str, int],
        details: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        stmt = (
            update(SqnsSyncRun)
            .where(SqnsSyncRun.id == run_id)
            .values(
                status=status,
                finished_at=finished_at,
                duration_ms=duration_ms,
                entities=entities,
                details=details,
                error=(error[:4000] if error else None),
                updated_at=finished_at,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def _sync_visits_history_backfill(
        self,
        *,
        visits_handler: SqnsVisitsSyncHandler,
        visits_cursor_state: dict[str, Any] | None,
        recent_date_from: date,
    ) -> tuple[int, dict[str, Any]]:
        state: dict[str, Any] = dict(visits_cursor_state or {})
        history_state = state.get(_VISITS_HISTORY_STATE_KEY)
        if not isinstance(history_state, dict):
            history_state = {}

        history_status = str(history_state.get("status") or "in_progress")
        if history_status == "completed":
            return 0, state

        history_start_date = self._resolve_visits_history_start_date()
        chunk_days = self._resolve_visits_history_chunk_days()
        next_date_till = self._parse_state_date(history_state.get("next_date_till")) or recent_date_from

        if next_date_till <= history_start_date:
            history_state.update(
                status="completed",
                next_date_till=history_start_date.isoformat(),
                history_start_date=history_start_date.isoformat(),
                chunk_days=chunk_days,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            state[_VISITS_HISTORY_STATE_KEY] = history_state
            return 0, state

        backfill_date_from = max(history_start_date, next_date_till - timedelta(days=chunk_days))
        backfill_date_till = next_date_till

        logger.info(
            "sqns_sync_visits_history_backfill_started",
            agent_id=str(self.agent_id),
            date_from=backfill_date_from.isoformat(),
            date_till=backfill_date_till.isoformat(),
            chunk_days=chunk_days,
            history_start_date=history_start_date.isoformat(),
        )
        backfill_result = await visits_handler.sync(
            date_from=backfill_date_from.isoformat(),
            date_till=backfill_date_till.isoformat(),
            modificate=None,
        )
        visits_synced = int(backfill_result.get("visits_synced", 0))
        next_backfill_date_till = backfill_date_from
        is_completed = next_backfill_date_till <= history_start_date

        history_state.update(
            status="completed" if is_completed else "in_progress",
            next_date_till=next_backfill_date_till.isoformat(),
            history_start_date=history_start_date.isoformat(),
            chunk_days=chunk_days,
            last_range_from=backfill_date_from.isoformat(),
            last_range_till=backfill_date_till.isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        state[_VISITS_HISTORY_STATE_KEY] = history_state

        logger.info(
            "sqns_sync_visits_history_backfill_completed",
            agent_id=str(self.agent_id),
            visits_synced=visits_synced,
            next_date_till=next_backfill_date_till.isoformat(),
            status=history_state["status"],
        )
        return visits_synced, state

    @staticmethod
    def _parse_state_date(value: Any) -> date | None:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _resolve_visits_history_start_date() -> date:
        return _VISITS_HISTORY_START_DATE

    @staticmethod
    def _resolve_visits_history_chunk_days() -> int:
        return _VISITS_HISTORY_CHUNK_DAYS

    @staticmethod
    def _resolve_visits_incremental_range() -> tuple[date, date]:
        settings = get_settings()
        window_days = min(max(settings.sqns_sync_visits_window_days, 1), 365)
        today = datetime.now(timezone.utc).date()
        date_from = today - timedelta(days=window_days)
        date_till = today
        return date_from, date_till

    @staticmethod
    def _resolve_payments_range() -> tuple[date, date]:
        settings = get_settings()
        window_days = min(max(settings.sqns_sync_payments_window_days, 1), 90)
        date_to = datetime.now(timezone.utc).date()
        date_from = date_to - timedelta(days=window_days)
        return date_from, date_to
