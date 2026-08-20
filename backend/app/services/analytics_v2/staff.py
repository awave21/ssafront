"""KPI per doctor / specialist (SqnsEmployee + SqnsVisit)."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics_v2 import (
    StaffClientLine,
    StaffDetailResponse,
    StaffMember,
    StaffOverviewResponse,
    StaffServiceLine,
    StaffSparkPoint,
)
from app.services.analytics import AnalyticsPeriod
from app.services.sqns.client_pii import decrypt_client_pii

logger = structlog.get_logger(__name__)


def _delta_pct(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100.0, 2)


_STAFF_AGG_SQL = text(
    """
    WITH visit_payments AS (
      SELECT visit_external_id, SUM(amount) AS total_amount
      FROM sqns_payments
      WHERE agent_id = :agent_id
        AND visit_external_id IS NOT NULL
      GROUP BY visit_external_id
    )
    SELECT
      e.external_id                AS resource_external_id,
      e.full_name                  AS full_name,
      e.position                   AS position,
      e.is_fired                   AS is_fired,
      COUNT(v.id) FILTER (WHERE NOT v.deleted)                     AS visits_total,
      COUNT(v.id) FILTER (WHERE v.attendance IS NOT NULL AND v.attendance > 0 AND NOT v.deleted) AS arrived_total,
      COUNT(v.id) FILTER (WHERE (v.attendance IS NULL OR v.attendance <= 0) AND NOT v.deleted) AS no_show_total,
      COUNT(v.id) FILTER (WHERE COALESCE(v.is_primary_per_resource, v.is_primary_visit) = true AND NOT v.deleted) AS primary_total,
      COUNT(v.id) FILTER (
        WHERE COALESCE(v.is_primary_per_resource, v.is_primary_visit) = true
          AND v.attendance IS NOT NULL AND v.attendance > 0 AND NOT v.deleted
      ) AS primary_arrived,
      COUNT(v.id) FILTER (
        WHERE COALESCE(v.is_primary_per_resource, v.is_primary_visit) = false AND NOT v.deleted
      ) AS repeat_total,
      COALESCE(SUM(COALESCE(vp.total_amount, 0)) FILTER (WHERE v.attendance IS NOT NULL AND v.attendance > 0 AND NOT v.deleted), 0) AS revenue_total,
      COALESCE(SUM(COALESCE(vp.total_amount, 0) - COALESCE(v.total_cost, 0))
        FILTER (WHERE v.attendance IS NOT NULL AND v.attendance > 0 AND NOT v.deleted), 0) AS margin_total
    FROM sqns_employees e
    LEFT JOIN sqns_visits v
      ON v.agent_id = e.agent_id
     AND v.resource_external_id = e.external_id
     AND v.visit_datetime >= :start_utc
     AND v.visit_datetime <  :end_utc
    LEFT JOIN visit_payments vp ON vp.visit_external_id = v.external_id::text
    WHERE e.agent_id = :agent_id
      AND e.is_deleted = false
    GROUP BY e.external_id, e.full_name, e.position, e.is_fired
    ORDER BY revenue_total DESC NULLS LAST, visits_total DESC, e.full_name ASC
    """
)


_PREV_AGG_SQL = text(
    """
    WITH visit_payments AS (
      SELECT visit_external_id, SUM(amount) AS total_amount
      FROM sqns_payments
      WHERE agent_id = :agent_id
        AND visit_external_id IS NOT NULL
      GROUP BY visit_external_id
    )
    SELECT
      v.resource_external_id AS resource_external_id,
      COUNT(v.id) FILTER (WHERE NOT v.deleted) AS visits_total,
      COALESCE(SUM(COALESCE(vp.total_amount, 0)) FILTER (WHERE v.attendance IS NOT NULL AND v.attendance > 0 AND NOT v.deleted), 0) AS revenue_total
    FROM sqns_visits v
    LEFT JOIN visit_payments vp ON vp.visit_external_id = v.external_id::text
    WHERE v.agent_id = :agent_id
      AND v.resource_external_id IS NOT NULL
      AND v.visit_datetime >= :start_utc
      AND v.visit_datetime <  :end_utc
    GROUP BY v.resource_external_id
    """
)


class StaffAnalyticsService:
    def __init__(self, db: AsyncSession, agent_id: UUID):
        self.db = db
        self.agent_id = agent_id

    async def get_overview(self, period: AnalyticsPeriod) -> StaffOverviewResponse:
        rows = (
            await self.db.execute(
                _STAFF_AGG_SQL,
                {
                    "agent_id": self.agent_id,
                    "start_utc": period.start_utc,
                    "end_utc": period.end_utc,
                },
            )
        ).mappings().all()

        prev_period_days = max((period.date_to - period.date_from).days + 1, 1)
        prev_start = period.start_utc - timedelta(days=prev_period_days)
        prev_end = period.start_utc
        prev_rows = (
            await self.db.execute(
                _PREV_AGG_SQL,
                {
                    "agent_id": self.agent_id,
                    "start_utc": prev_start,
                    "end_utc": prev_end,
                },
            )
        ).mappings().all()
        prev_by_resource: dict[int, dict[str, float]] = {
            int(r["resource_external_id"]): {
                "visits": float(r["visits_total"] or 0),
                "revenue": float(r["revenue_total"] or 0),
            }
            for r in prev_rows
        }

        items: list[StaffMember] = []
        for row in rows:
            visits = int(row["visits_total"] or 0)
            arrived = int(row["arrived_total"] or 0)
            no_show = max(visits - arrived, 0)
            revenue = float(row["revenue_total"] or 0)
            ext_id = int(row["resource_external_id"])
            prev = prev_by_resource.get(ext_id)
            items.append(
                StaffMember(
                    resource_external_id=ext_id,
                    full_name=row["full_name"] or f"#{ext_id}",
                    position=row["position"],
                    is_fired=bool(row["is_fired"]),
                    visits_total=visits,
                    arrived_total=arrived,
                    no_show_total=no_show,
                    no_show_pct=round((no_show / visits) * 100.0, 1) if visits else 0.0,
                    primary_total=int(row["primary_total"] or 0),
                    primary_arrived=int(row["primary_arrived"] or 0),
                    repeat_total=int(row["repeat_total"] or 0),
                    conversion_pct=round((arrived / visits) * 100.0, 1) if visits else 0.0,
                    revenue_total=revenue,
                    margin_total=float(row["margin_total"] or 0),
                    avg_check=round(revenue / arrived, 2) if arrived else 0.0,
                    revenue_delta_pct=_delta_pct(revenue, prev["revenue"]) if prev else None,
                    visits_delta_pct=_delta_pct(visits, prev["visits"]) if prev else None,
                )
            )

        return StaffOverviewResponse(
            period_start=period.start_local,
            period_end=period.end_local_exclusive,
            timezone=period.timezone_name,
            items=items,
            employees_total=len(items),
        )

    async def get_detail(
        self,
        period: AnalyticsPeriod,
        resource_external_id: int,
    ) -> StaffDetailResponse | None:
        rows = (
            await self.db.execute(
                _STAFF_AGG_SQL,
                {
                    "agent_id": self.agent_id,
                    "start_utc": period.start_utc,
                    "end_utc": period.end_utc,
                },
            )
        ).mappings().all()
        target = next((r for r in rows if int(r["resource_external_id"]) == resource_external_id), None)
        if target is None:
            return None

        member_block = (await self.get_overview(period)).items
        member = next((m for m in member_block if m.resource_external_id == resource_external_id), None)
        if member is None:
            return None

        services_rows = (
            await self.db.execute(
                text(
                    """
                    WITH service_items AS (
                      SELECT
                        v.id AS visit_id,
                        v.attendance,
                        COALESCE(v.is_primary_per_resource, v.is_primary_visit) AS is_primary,
                        jsonb_array_elements(
                          COALESCE(v.raw_data -> 'services', '[]'::jsonb)
                        ) AS svc
                      FROM sqns_visits v
                      WHERE v.agent_id = :agent_id
                        AND v.resource_external_id = :resource_id
                        AND v.visit_datetime >= :start_utc
                        AND v.visit_datetime <  :end_utc
                        AND NOT v.deleted
                    )
                    SELECT
                      NULLIF(svc->>'id', '')::bigint AS service_external_id,
                      COALESCE(svc->>'name', svc->>'title', 'Услуга') AS service_name,
                      COUNT(*) AS bookings_total,
                      COUNT(*) FILTER (WHERE attendance IS NOT NULL AND attendance > 0) AS arrived_total,
                      COUNT(*) FILTER (WHERE attendance IS NULL OR attendance <= 0) AS no_show_total,
                      COUNT(*) FILTER (WHERE is_primary = true) AS primary_total,
                      COUNT(*) FILTER (WHERE is_primary = false) AS repeat_total,
                      COALESCE(
                        SUM(
                          COALESCE(
                            NULLIF(svc->>'paySum', '')::numeric,
                            NULLIF(svc->>'totalAmount', '')::numeric,
                            NULLIF(svc->>'price', '')::numeric * COALESCE(NULLIF(svc->>'amount', '')::numeric, 1),
                            0
                          )
                        ),
                        0
                      ) AS revenue_total
                    FROM service_items
                    GROUP BY 1, 2
                    ORDER BY revenue_total DESC NULLS LAST, bookings_total DESC
                    """
                ),
                {
                    "agent_id": self.agent_id,
                    "resource_id": resource_external_id,
                    "start_utc": period.start_utc,
                    "end_utc": period.end_utc,
                },
            )
        ).mappings().all()
        top_services: list[StaffServiceLine] = []
        for r in services_rows:
            bookings = int(r["bookings_total"] or 0)
            arrived = int(r["arrived_total"] or 0)
            no_show = int(r["no_show_total"] or 0)
            revenue = float(r["revenue_total"] or 0)
            top_services.append(
                StaffServiceLine(
                    service_external_id=int(r["service_external_id"]) if r["service_external_id"] is not None else None,
                    service_name=r["service_name"] or "—",
                    bookings_total=bookings,
                    arrived_total=arrived,
                    no_show_total=no_show,
                    primary_total=int(r["primary_total"] or 0),
                    repeat_total=int(r["repeat_total"] or 0),
                    revenue_total=revenue,
                    avg_check=round(revenue / bookings, 2) if bookings else 0.0,
                    conversion_pct=round((arrived / bookings) * 100.0, 1) if bookings else 0.0,
                    no_show_pct=round((no_show / bookings) * 100.0, 1) if bookings else 0.0,
                )
            )

        clients_rows = (
            await self.db.execute(
                text(
                    """
                    SELECT
                      v.client_external_id,
                      COUNT(*) AS visits_total,
                      COUNT(*) FILTER (WHERE v.attendance IS NOT NULL AND v.attendance > 0) AS arrived_total,
                      COUNT(*) FILTER (WHERE v.attendance IS NULL OR v.attendance <= 0) AS no_show_total,
                      COUNT(*) FILTER (WHERE COALESCE(v.is_primary_per_resource, v.is_primary_visit) = true) AS primary_total,
                      COUNT(*) FILTER (WHERE COALESCE(v.is_primary_per_resource, v.is_primary_visit) = false) AS repeat_total,
                      COALESCE(SUM(v.total_price), 0) AS revenue_total,
                      MAX(v.visit_datetime) AS last_visit_at,
                      c.pii_data AS pii_data
                    FROM sqns_visits v
                    LEFT JOIN sqns_clients c
                      ON c.agent_id = v.agent_id AND c.external_id = v.client_external_id
                    WHERE v.agent_id = :agent_id
                      AND v.resource_external_id = :resource_id
                      AND v.visit_datetime >= :start_utc
                      AND v.visit_datetime <  :end_utc
                      AND NOT v.deleted
                      AND v.client_external_id IS NOT NULL
                    GROUP BY v.client_external_id, c.pii_data
                    ORDER BY revenue_total DESC NULLS LAST, visits_total DESC
                    """
                ),
                {
                    "agent_id": self.agent_id,
                    "resource_id": resource_external_id,
                    "start_utc": period.start_utc,
                    "end_utc": period.end_utc,
                },
            )
        ).mappings().all()
        clients: list[StaffClientLine] = []
        for r in clients_rows:
            pii = decrypt_client_pii(r["pii_data"]) if r["pii_data"] else {}
            parts = [pii.get("lastname"), pii.get("firstname"), pii.get("patronymic")]
            full_name = " ".join(p for p in parts if p) or f"Клиент #{r['client_external_id']}"
            visits = int(r["visits_total"] or 0)
            arrived = int(r["arrived_total"] or 0)
            revenue = float(r["revenue_total"] or 0)
            clients.append(
                StaffClientLine(
                    client_external_id=int(r["client_external_id"]),
                    full_name=full_name,
                    phone=pii.get("phone"),
                    visits_total=visits,
                    arrived_total=arrived,
                    no_show_total=int(r["no_show_total"] or 0),
                    primary_total=int(r["primary_total"] or 0),
                    repeat_total=int(r["repeat_total"] or 0),
                    revenue_total=revenue,
                    avg_check=round(revenue / visits, 2) if visits else 0.0,
                    last_visit_at=r["last_visit_at"],
                )
            )

        spark_rows = (
            await self.db.execute(
                text(
                    """
                    WITH visit_payments AS (
                      SELECT visit_external_id, SUM(amount) AS total_amount
                      FROM sqns_payments
                      WHERE agent_id = :agent_id AND visit_external_id IS NOT NULL
                      GROUP BY visit_external_id
                    )
                    SELECT
                      to_char(date_trunc('day', v.visit_datetime AT TIME ZONE :tz), 'YYYY-MM-DD') AS bucket,
                      COUNT(*) AS visits,
                      COALESCE(SUM(COALESCE(vp.total_amount, 0)) FILTER (WHERE v.attendance IS NOT NULL AND v.attendance > 0), 0) AS revenue
                    FROM sqns_visits v
                    LEFT JOIN visit_payments vp ON vp.visit_external_id = v.external_id::text
                    WHERE v.agent_id = :agent_id
                      AND v.resource_external_id = :resource_id
                      AND v.visit_datetime >= :start_utc
                      AND v.visit_datetime <  :end_utc
                      AND NOT v.deleted
                    GROUP BY 1
                    ORDER BY 1
                    """
                ),
                {
                    "agent_id": self.agent_id,
                    "resource_id": resource_external_id,
                    "start_utc": period.start_utc,
                    "end_utc": period.end_utc,
                    "tz": period.timezone_name,
                },
            )
        ).mappings().all()
        sparkline = [
            StaffSparkPoint(bucket=r["bucket"], visits=int(r["visits"] or 0), revenue=float(r["revenue"] or 0))
            for r in spark_rows
        ]

        return StaffDetailResponse(
            period_start=period.start_local,
            period_end=period.end_local_exclusive,
            timezone=period.timezone_name,
            staff=member,
            top_services=top_services,
            clients=clients,
            sparkline=sparkline,
        )
