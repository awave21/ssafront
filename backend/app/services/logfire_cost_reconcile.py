from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Awaitable
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.run import Run
from app.db.session import async_session_factory
from app.services.tenant_balance import sync_run_balance_charge

logger = structlog.get_logger(__name__)

_COST_QUANT = Decimal("0.0000000001")


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value)).quantize(_COST_QUANT, rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _extract_cost_from_payload(payload: Any) -> Decimal | None:
    if isinstance(payload, dict):
        direct = payload.get("cost_usd_logfire")
        if isinstance(direct, list):
            return _to_decimal(direct[0] if direct else None)
        if direct is not None:
            return _to_decimal(direct)

        rows = payload.get("rows")
        if isinstance(rows, list) and rows:
            first = rows[0]
            if isinstance(first, dict):
                return _to_decimal(first.get("cost_usd_logfire"))
            if isinstance(first, list) and first:
                return _to_decimal(first[0])

        data = payload.get("data")
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                return _to_decimal(first.get("cost_usd_logfire"))

    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            return _to_decimal(first.get("cost_usd_logfire"))
    return None


def _build_cost_sql(run_id: UUID, trace_id: str) -> str:
    safe_run_id = str(run_id).replace("'", "''")
    safe_trace_id = str(trace_id).replace("'", "''")
    return f"""
SELECT
  CAST(NULLIF(attributes->'logfire.metrics'->'operation.cost'->>'total', '') AS DOUBLE PRECISION) AS cost_usd_logfire
FROM records
WHERE attributes->>'run_id' = '{safe_run_id}'
  AND attributes->>'trace_id' = '{safe_trace_id}'
ORDER BY start_timestamp DESC
LIMIT 1
"""


async def _fetch_logfire_cost_usd(run_id: UUID, trace_id: str) -> Decimal | None:
    settings = get_settings()
    if not settings.logfire_read_token:
        return None

    query_sql = _build_cost_sql(run_id, trace_id)
    headers = {
        "Authorization": f"Bearer {settings.logfire_read_token}",
        "Accept": "application/json",
    }
    params = {"sql": query_sql}

    async with httpx.AsyncClient(timeout=settings.logfire_reconcile_timeout_seconds) as client:
        response = await client.get(f"{settings.logfire_base_url}/v1/query", headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
        return _extract_cost_from_payload(payload)


async def _update_run_reconcile_state(
    db: AsyncSession,
    *,
    run_id: UUID,
    status: str,
    attempts: int | None = None,
    error: str | None = None,
    cost_usd_logfire: Decimal | None = None,
    reconciled_at: datetime | None = None,
) -> None:
    stmt = select(Run).where(Run.id == run_id).limit(1)
    run = (await db.execute(stmt)).scalar_one_or_none()
    if run is None:
        return

    run.logfire_reconcile_status = status
    if attempts is not None:
        run.logfire_reconcile_attempts = attempts
    run.logfire_reconcile_error = error
    if cost_usd_logfire is not None:
        run.cost_usd_logfire = cost_usd_logfire
    if status == "succeeded":
        await sync_run_balance_charge(db, run=run)
    if reconciled_at is not None:
        run.logfire_reconciled_at = reconciled_at
    await db.commit()


async def reconcile_run_cost_from_logfire(
    *,
    run_id: UUID,
    trace_id: str,
    db_session_factory: Callable[[], Awaitable[AsyncSession]] | Callable[[], Any] = async_session_factory,
) -> None:
    settings = get_settings()
    if not settings.logfire_reconcile_enabled:
        async with db_session_factory() as db:
            await _update_run_reconcile_state(
                db,
                run_id=run_id,
                status="skipped",
                error="reconcile_disabled",
                reconciled_at=datetime.utcnow(),
            )
        return

    if not settings.logfire_read_token:
        async with db_session_factory() as db:
            await _update_run_reconcile_state(
                db,
                run_id=run_id,
                status="skipped",
                error="logfire_read_token_missing",
                reconciled_at=datetime.utcnow(),
            )
        return

    if settings.logfire_reconcile_initial_delay_seconds > 0:
        await asyncio.sleep(settings.logfire_reconcile_initial_delay_seconds)

    max_attempts = max(settings.logfire_reconcile_max_attempts, 1)
    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        async with db_session_factory() as db:
            await _update_run_reconcile_state(
                db,
                run_id=run_id,
                status="processing",
                attempts=attempt,
                error=None,
            )

        try:
            cost_usd_logfire = await _fetch_logfire_cost_usd(run_id, trace_id)
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "logfire_cost_fetch_error",
                run_id=str(run_id),
                trace_id=trace_id,
                attempt=attempt,
                error=last_error,
            )
            if attempt < max_attempts:
                await asyncio.sleep(settings.logfire_reconcile_retry_delay_seconds)
            continue

        if cost_usd_logfire is not None:
            async with db_session_factory() as db:
                await _update_run_reconcile_state(
                    db,
                    run_id=run_id,
                    status="succeeded",
                    attempts=attempt,
                    error=None,
                    cost_usd_logfire=cost_usd_logfire,
                    reconciled_at=datetime.utcnow(),
                )
            return

        if attempt < max_attempts:
            await asyncio.sleep(settings.logfire_reconcile_retry_delay_seconds)

    async with db_session_factory() as db:
        if last_error:
            await _update_run_reconcile_state(
                db,
                run_id=run_id,
                status="failed",
                attempts=max_attempts,
                error=last_error[:2000],
                reconciled_at=datetime.utcnow(),
            )
        else:
            await _update_run_reconcile_state(
                db,
                run_id=run_id,
                status="no_data",
                attempts=max_attempts,
                error=None,
                reconciled_at=datetime.utcnow(),
            )


def schedule_logfire_cost_reconcile(*, run_id: UUID, trace_id: str) -> None:
    async def _runner() -> None:
        try:
            await reconcile_run_cost_from_logfire(run_id=run_id, trace_id=trace_id)
        except Exception as exc:
            logger.exception(
                "logfire_reconcile_task_failed",
                run_id=str(run_id),
                trace_id=trace_id,
                error=str(exc),
            )

    asyncio.create_task(_runner())
