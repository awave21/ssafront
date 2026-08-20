"""Pydantic schemas for staff motivation report."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MotivationRuleResponse(BaseModel):
    primary_pct_low: float = Field(description="% с первички при среднем чеке ниже нормы")
    primary_pct_norm: float = Field(description="% с первички при нормальном среднем чеке")
    primary_pct_high: float = Field(description="% с первички при высоком среднем чеке")
    repeat_pct_low: float = Field(description="% со вторички при среднем чеке ниже нормы")
    repeat_pct_norm: float = Field(description="% со вторички при нормальном среднем чеке")
    repeat_pct_high: float = Field(description="% со вторички при высоком среднем чеке")
    avg_check_low: float = Field(description="Нижняя граница нормы среднего чека первичных")
    avg_check_high: float = Field(description="Верхняя граница нормы (выше → бонусный %)")
    include_commodities: bool = Field(description="Учитывать товары в выручке для расчёта бонуса")


class MotivationRuleUpdate(BaseModel):
    primary_pct_low: float | None = None
    primary_pct_norm: float | None = None
    primary_pct_high: float | None = None
    repeat_pct_low: float | None = None
    repeat_pct_norm: float | None = None
    repeat_pct_high: float | None = None
    avg_check_low: float | None = None
    avg_check_high: float | None = None
    include_commodities: bool | None = None


MotivationTier = Literal["low", "norm", "high", "no_primary"]


class MotivationMember(BaseModel):
    resource_external_id: int
    full_name: str
    position: str | None = None
    is_fired: bool = False

    visits_total: int = 0
    arrived_total: int = 0
    primary_visits: int = 0
    repeat_visits: int = 0

    # Выручка по типам (всегда, независимо от include_commodities)
    services_revenue: float = 0.0
    commodities_revenue: float = 0.0
    revenue_total: float = Field(default=0.0, description="services + commodities")

    # Выручка для расчёта бонуса (с учётом include_commodities)
    bonusable_revenue: float = 0.0
    primary_revenue: float = 0.0
    repeat_revenue: float = 0.0

    # Средние чеки
    primary_avg_check: float = 0.0
    repeat_avg_check: float = 0.0
    total_avg_check: float = 0.0

    tier: MotivationTier = "norm"
    applied_primary_pct: float = 0.0
    applied_repeat_pct: float = 0.0

    bonus_primary: float = 0.0
    bonus_repeat: float = 0.0
    bonus_total: float = 0.0


class MotivationTotals(BaseModel):
    revenue_total: float = 0.0
    services_revenue: float = 0.0
    commodities_revenue: float = 0.0
    primary_revenue: float = 0.0
    repeat_revenue: float = 0.0
    bonus_total: float = 0.0


class MotivationOverviewResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    timezone: str
    rule: MotivationRuleResponse
    items: list[MotivationMember] = Field(default_factory=list)
    totals: MotivationTotals = Field(default_factory=MotivationTotals)
