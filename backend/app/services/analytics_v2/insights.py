"""Deterministic rules engine for analytics insights."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics_v2 import Insight, InsightsResponse
from app.services.analytics import AnalyticsPeriod
from app.services.analytics_v2.bot_health import BotHealthService
from app.services.analytics_v2.staff import StaffAnalyticsService

logger = structlog.get_logger(__name__)


class InsightsService:
    def __init__(self, db: AsyncSession, agent_id: UUID, tenant_id: UUID):
        self.db = db
        self.agent_id = agent_id
        self.tenant_id = tenant_id

    async def collect(self, period: AnalyticsPeriod) -> InsightsResponse:
        items: list[Insight] = []

        items.extend(await self._staff_rules(period))
        items.extend(await self._bot_rules(period))
        items.extend(await self._dialog_rules(period))

        items.sort(key=lambda i: {"critical": 0, "warning": 1, "info": 2}[i.severity])

        return InsightsResponse(
            period_start=period.start_local,
            period_end=period.end_local_exclusive,
            timezone=period.timezone_name,
            items=items[:20],
        )

    async def _staff_rules(self, period: AnalyticsPeriod) -> list[Insight]:
        out: list[Insight] = []
        try:
            staff = await StaffAnalyticsService(self.db, self.agent_id).get_overview(period)
        except Exception:
            logger.exception("insights_staff_failed")
            return out

        for member in staff.items:
            if member.no_show_pct >= 25 and member.visits_total >= 5:
                out.append(
                    Insight(
                        code="staff_no_show_high",
                        severity="warning",
                        category="staff",
                        title=f"{member.full_name}: высокий no-show",
                        body=(
                            f"Из {member.visits_total} записей не дошли {member.no_show_total} "
                            f"({member.no_show_pct}%). Норма ≤ 15%. Стоит усилить напоминания и подтверждения."
                        ),
                        metric_value=member.no_show_pct,
                        metric_label="no-show %",
                        entity_type="staff",
                        entity_id=str(member.resource_external_id),
                        action_tab="staff",
                    )
                )
            if member.revenue_delta_pct is not None and member.revenue_delta_pct <= -20 and member.visits_total >= 5:
                out.append(
                    Insight(
                        code="staff_revenue_drop",
                        severity="critical" if member.revenue_delta_pct <= -40 else "warning",
                        category="staff",
                        title=f"{member.full_name}: выручка снижается",
                        body=(
                            f"Выручка {member.revenue_total:,.0f} ₽ — "
                            f"{member.revenue_delta_pct:+.1f}% к прошлому периоду. "
                            "Проверить расписание, структуру услуг и удержание клиентов."
                        ),
                        metric_value=member.revenue_delta_pct,
                        metric_label="Δ выручки %",
                        entity_type="staff",
                        entity_id=str(member.resource_external_id),
                        action_tab="staff",
                    )
                )
            if member.conversion_pct < 50 and member.visits_total >= 10:
                out.append(
                    Insight(
                        code="staff_conversion_low",
                        severity="warning",
                        category="staff",
                        title=f"{member.full_name}: низкая конверсия в дошедших",
                        body=(
                            f"Конверсия {member.conversion_pct}% при {member.visits_total} записях. "
                            "Большая часть пациентов записывается, но не приходит."
                        ),
                        metric_value=member.conversion_pct,
                        metric_label="конверсия %",
                        entity_type="staff",
                        entity_id=str(member.resource_external_id),
                        action_tab="staff",
                    )
                )
        return out

    async def _bot_rules(self, period: AnalyticsPeriod) -> list[Insight]:
        out: list[Insight] = []
        try:
            health = await BotHealthService(self.db, self.agent_id, self.tenant_id).get_health(period)
        except Exception:
            logger.exception("insights_bot_failed")
            return out

        b = health.budget
        if b.spent_pct >= 80:
            out.append(
                Insight(
                    code="bot_budget_burn",
                    severity="critical" if b.spent_pct >= 95 else "warning",
                    category="budget",
                    title="Баланс бота близок к исчерпанию",
                    body=(
                        f"Потрачено {b.spent_usd:.2f}$ из {b.initial_balance_usd:.2f}$ "
                        f"({b.spent_pct}%). При текущем темпе хватит на {b.days_to_zero or '∞'} дней."
                    ),
                    metric_value=b.spent_pct,
                    metric_label="spent %",
                    action_tab="bot",
                )
            )

        for tool in health.tools[:10]:
            if tool.error_pct >= 10 and tool.calls_total >= 20:
                out.append(
                    Insight(
                        code="bot_tool_error_spike",
                        severity="warning",
                        category="bot",
                        title=f"Тул `{tool.tool_name}`: всплеск ошибок",
                        body=(
                            f"{tool.error_count} ошибок из {tool.calls_total} вызовов "
                            f"({tool.error_pct}%). Проверить интеграцию и payload."
                        ),
                        metric_value=tool.error_pct,
                        metric_label="error %",
                        action_tab="bot",
                    )
                )

        if health.runs.runs_total >= 50 and health.runs.success_pct < 90:
            out.append(
                Insight(
                    code="bot_runs_failing",
                    severity="warning",
                    category="bot",
                    title="Падает доля успешных запусков",
                    body=(
                        f"Успешных runs {health.runs.success_pct}% при {health.runs.runs_total} запусках. "
                        "Проверьте логи и валидаторы агента."
                    ),
                    metric_value=health.runs.success_pct,
                    metric_label="success %",
                    action_tab="bot",
                )
            )

        if health.dialogs.dialogs_total >= 20 and health.dialogs.autonomy_pct < 60:
            out.append(
                Insight(
                    code="bot_low_autonomy",
                    severity="info",
                    category="bot",
                    title="Менеджеры часто вмешиваются в диалоги",
                    body=(
                        f"Только {health.dialogs.autonomy_pct}% диалогов прошли без оператора "
                        f"(всего {health.dialogs.dialogs_total}). Стоит усилить промпт или добавить правила."
                    ),
                    metric_value=health.dialogs.autonomy_pct,
                    metric_label="autonomy %",
                    action_tab="managers",
                )
            )
        return out

    async def _dialog_rules(self, period: AnalyticsPeriod) -> list[Insight]:
        out: list[Insight] = []
        try:
            stuck = (
                await self.db.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM dialog_states
                        WHERE agent_id = :agent_id
                          AND status = 'active'
                          AND last_user_message_at IS NOT NULL
                          AND last_user_message_at < :threshold
                          AND (last_manager_message_at IS NULL OR last_manager_message_at < last_user_message_at)
                        """
                    ),
                    {
                        "agent_id": self.agent_id,
                        "threshold": datetime.utcnow() - timedelta(hours=24),
                    },
                )
            ).scalar() or 0
        except Exception:
            stuck = 0

        if stuck >= 3:
            out.append(
                Insight(
                    code="dialog_stuck",
                    severity="warning",
                    category="dialog",
                    title=f"{stuck} диалогов без ответа > 24ч",
                    body=(
                        "Клиенты написали, но ни бот, ни менеджер не ответили. "
                        "Откройте вкладку Диалоги и разберите."
                    ),
                    metric_value=float(stuck),
                    metric_label="dialogs",
                    action_url="/dialogs",
                )
            )
        return out
