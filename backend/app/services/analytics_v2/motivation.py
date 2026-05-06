"""Motivation (bonus) calculation for doctors per period."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.motivation_rule import MotivationRule
from app.schemas.motivation import (
    MotivationMember,
    MotivationOverviewResponse,
    MotivationRuleResponse,
    MotivationRuleUpdate,
    MotivationTier,
    MotivationTotals,
)
from app.services.analytics import AnalyticsPeriod

logger = structlog.get_logger(__name__)

# Оплаты типа "услуги": service-sell, alternative-payment, certificate-sell
_SERVICE_HANDLES = ("service-sell", "alternative-payment", "certificate-sell")
# Оплаты типа "товары": commodity-sell
_COMMODITY_HANDLE = "commodity-sell"

_MOTIVATION_SQL = text(
    """
    WITH visit_payments AS (
      SELECT
        v.id AS visit_id,
        COALESCE(SUM(p.amount) FILTER (
          WHERE p.payment_type_handle IN ('service-sell', 'alternative-payment', 'certificate-sell')
        ), 0) AS services_paid,
        COALESCE(SUM(p.amount) FILTER (
          WHERE p.payment_type_handle = 'commodity-sell'
        ), 0) AS commodities_paid
      FROM sqns_visits v
      LEFT JOIN sqns_payments p
        ON p.visit_external_id = v.external_id::text
       AND p.agent_id = v.agent_id
      WHERE v.agent_id = :agent_id
        AND v.deleted = false
        AND v.attendance IS NOT NULL AND v.attendance > 0
        AND v.visit_datetime >= :start_utc
        AND v.visit_datetime < :end_utc
      GROUP BY v.id
    )
    SELECT
      e.external_id                                     AS resource_external_id,
      e.full_name                                       AS full_name,
      e.position                                        AS position,
      e.is_fired                                        AS is_fired,
      COUNT(v.id) FILTER (WHERE NOT v.deleted)          AS visits_total,
      COUNT(v.id) FILTER (
        WHERE v.attendance IS NOT NULL AND v.attendance > 0 AND NOT v.deleted
      )                                                 AS arrived_total,
      COUNT(v.id) FILTER (
        WHERE COALESCE(v.is_primary_per_resource, v.is_primary_visit) = true
          AND v.attendance IS NOT NULL AND v.attendance > 0 AND NOT v.deleted
      )                                                 AS primary_visits,
      COUNT(v.id) FILTER (
        WHERE COALESCE(v.is_primary_per_resource, v.is_primary_visit) = false
          AND v.attendance IS NOT NULL AND v.attendance > 0 AND NOT v.deleted
      )                                                 AS repeat_visits,
      COALESCE(SUM(vp.services_paid), 0)                AS services_revenue,
      COALESCE(SUM(vp.commodities_paid), 0)             AS commodities_revenue,
      COALESCE(SUM(vp.services_paid) FILTER (
        WHERE COALESCE(v.is_primary_per_resource, v.is_primary_visit) = true
      ), 0)                                             AS services_primary,
      COALESCE(SUM(vp.commodities_paid) FILTER (
        WHERE COALESCE(v.is_primary_per_resource, v.is_primary_visit) = true
      ), 0)                                             AS commodities_primary
    FROM sqns_employees e
    LEFT JOIN sqns_visits v
      ON v.agent_id = e.agent_id
     AND v.resource_external_id = e.external_id
     AND v.deleted = false
     AND v.attendance IS NOT NULL AND v.attendance > 0
     AND v.visit_datetime >= :start_utc
     AND v.visit_datetime < :end_utc
    LEFT JOIN visit_payments vp ON vp.visit_id = v.id
    WHERE e.agent_id = :agent_id
      AND e.is_deleted = false
    GROUP BY e.external_id, e.full_name, e.position, e.is_fired
    HAVING COUNT(v.id) FILTER (WHERE NOT v.deleted) > 0
    ORDER BY
      (COALESCE(SUM(vp.services_paid), 0) + COALESCE(SUM(vp.commodities_paid), 0)) DESC NULLS LAST,
      e.full_name ASC
    """
)

_DEFAULT_RULE = MotivationRule(
    tenant_id=UUID("00000000-0000-0000-0000-000000000000"),
    role="doctor",
)


def _classify_tier(
    primary_avg_check: float,
    primary_visits: int,
    avg_check_low: float,
    avg_check_high: float,
) -> MotivationTier:
    if primary_visits == 0:
        # нет первичных визитов — не штрафуем, считаем как норма
        return "no_primary"
    if primary_avg_check < avg_check_low:
        return "low"
    if primary_avg_check > avg_check_high:
        return "high"
    return "norm"


def _rule_to_response(rule: MotivationRule) -> MotivationRuleResponse:
    return MotivationRuleResponse(
        primary_pct=float(rule.primary_pct),
        repeat_pct_low=float(rule.repeat_pct_low),
        repeat_pct_norm=float(rule.repeat_pct_norm),
        repeat_pct_high=float(rule.repeat_pct_high),
        avg_check_low=float(rule.avg_check_low),
        avg_check_high=float(rule.avg_check_high),
        include_commodities=rule.include_commodities,
    )


class MotivationService:
    def __init__(self, db: AsyncSession, agent_id: UUID, tenant_id: UUID):
        self.db = db
        self.agent_id = agent_id
        self.tenant_id = tenant_id

    async def _get_or_create_rule(self, role: str = "doctor") -> MotivationRule:
        result = await self.db.execute(
            select(MotivationRule).where(
                MotivationRule.tenant_id == self.tenant_id,
                MotivationRule.role == role,
            )
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            rule = MotivationRule(tenant_id=self.tenant_id, role=role)
            self.db.add(rule)
            await self.db.flush()
        return rule

    async def get_rule(self, role: str = "doctor") -> MotivationRuleResponse:
        rule = await self._get_or_create_rule(role)
        return _rule_to_response(rule)

    async def update_rule(self, payload: MotivationRuleUpdate, role: str = "doctor") -> MotivationRuleResponse:
        rule = await self._get_or_create_rule(role)
        if payload.primary_pct is not None:
            rule.primary_pct = Decimal(str(payload.primary_pct))
        if payload.repeat_pct_low is not None:
            rule.repeat_pct_low = Decimal(str(payload.repeat_pct_low))
        if payload.repeat_pct_norm is not None:
            rule.repeat_pct_norm = Decimal(str(payload.repeat_pct_norm))
        if payload.repeat_pct_high is not None:
            rule.repeat_pct_high = Decimal(str(payload.repeat_pct_high))
        if payload.avg_check_low is not None:
            rule.avg_check_low = Decimal(str(payload.avg_check_low))
        if payload.avg_check_high is not None:
            rule.avg_check_high = Decimal(str(payload.avg_check_high))
        if payload.include_commodities is not None:
            rule.include_commodities = payload.include_commodities
        await self.db.flush()
        return _rule_to_response(rule)

    async def get_overview(self, period: AnalyticsPeriod) -> MotivationOverviewResponse:
        rule = await self._get_or_create_rule("doctor")
        rule_resp = _rule_to_response(rule)

        rows = (
            await self.db.execute(
                _MOTIVATION_SQL,
                {
                    "agent_id": self.agent_id,
                    "start_utc": period.start_utc,
                    "end_utc": period.end_utc,
                },
            )
        ).mappings().all()

        items: list[MotivationMember] = []
        for row in rows:
            primary_visits = int(row["primary_visits"] or 0)
            repeat_visits = int(row["repeat_visits"] or 0)
            arrived = int(row["arrived_total"] or 0)
            services_rev = float(row["services_revenue"] or 0)
            commodities_rev = float(row["commodities_revenue"] or 0)
            services_primary = float(row["services_primary"] or 0)
            commodities_primary = float(row["commodities_primary"] or 0)

            revenue_total = services_rev + commodities_rev
            # бонус считается только от услуг, товары — только для отображения
            bonusable = services_rev
            primary_bonusable = services_primary
            repeat_bonusable = bonusable - primary_bonusable

            primary_avg = round(primary_bonusable / primary_visits, 2) if primary_visits else 0.0
            repeat_avg = round(repeat_bonusable / repeat_visits, 2) if repeat_visits else 0.0
            total_avg = round(revenue_total / arrived, 2) if arrived else 0.0

            tier = _classify_tier(primary_avg, primary_visits, rule_resp.avg_check_low, rule_resp.avg_check_high)

            if tier == "low":
                applied_pct = rule_resp.repeat_pct_low
            elif tier == "high":
                applied_pct = rule_resp.repeat_pct_high
            else:
                # norm или no_primary — норма
                applied_pct = rule_resp.repeat_pct_norm

            bonus_primary = round(primary_bonusable * rule_resp.primary_pct / 100, 2)
            bonus_repeat = round(repeat_bonusable * applied_pct / 100, 2)

            items.append(
                MotivationMember(
                    resource_external_id=int(row["resource_external_id"]),
                    full_name=row["full_name"] or f"#{row['resource_external_id']}",
                    position=row["position"],
                    is_fired=bool(row["is_fired"]),
                    visits_total=int(row["visits_total"] or 0),
                    arrived_total=arrived,
                    primary_visits=primary_visits,
                    repeat_visits=repeat_visits,
                    services_revenue=round(services_rev, 2),
                    commodities_revenue=round(commodities_rev, 2),
                    revenue_total=round(revenue_total, 2),
                    bonusable_revenue=round(bonusable, 2),
                    primary_revenue=round(primary_bonusable, 2),
                    repeat_revenue=round(repeat_bonusable, 2),
                    primary_avg_check=primary_avg,
                    repeat_avg_check=repeat_avg,
                    total_avg_check=total_avg,
                    tier=tier,
                    applied_repeat_pct=applied_pct,
                    bonus_primary=bonus_primary,
                    bonus_repeat=bonus_repeat,
                    bonus_total=round(bonus_primary + bonus_repeat, 2),
                )
            )

        totals = MotivationTotals(
            revenue_total=round(sum(m.revenue_total for m in items), 2),
            services_revenue=round(sum(m.services_revenue for m in items), 2),
            commodities_revenue=round(sum(m.commodities_revenue for m in items), 2),
            primary_revenue=round(sum(m.primary_revenue for m in items), 2),
            repeat_revenue=round(sum(m.repeat_revenue for m in items), 2),
            bonus_total=round(sum(m.bonus_total for m in items), 2),
        )

        return MotivationOverviewResponse(
            period_start=period.start_local,
            period_end=period.end_local_exclusive,
            timezone=period.timezone_name,
            rule=rule_resp,
            items=items,
            totals=totals,
        )
