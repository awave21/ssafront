"""Bot health KPIs: runs, tool calls, dialog quality, budget burn."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics_v2 import (
    BotBudget,
    BotDialogQuality,
    BotHealthResponse,
    BotRunsKpi,
    BotToolStat,
    FunnelResponse,
    FunnelStage,
)
from app.services.analytics import AnalyticsPeriod

logger = structlog.get_logger(__name__)


class BotHealthService:
    def __init__(self, db: AsyncSession, agent_id: UUID, tenant_id: UUID):
        self.db = db
        self.agent_id = agent_id
        self.tenant_id = tenant_id

    async def get_health(self, period: AnalyticsPeriod) -> BotHealthResponse:
        runs = await self._runs_kpi(period)
        tools = await self._tool_stats(period)
        dialogs = await self._dialog_quality(period)
        budget = await self._budget(period)
        return BotHealthResponse(
            period_start=period.start_local,
            period_end=period.end_local_exclusive,
            timezone=period.timezone_name,
            runs=runs,
            tools=tools,
            dialogs=dialogs,
            budget=budget,
        )

    async def get_funnel(self, period: AnalyticsPeriod) -> FunnelResponse:
        # 1. написал в чат — runs (входящих сообщений ~ runs.input_message)
        # 2. бот ответил — runs со статусом succeeded и непустым output
        # 3. запись создана — sqns_visits в периоде
        # 4. дошёл — attendance > 0
        # 5. оплатил — sqns_payments c amount > 0
        # 6. повторно записался — sqns_visits с is_primary=false
        try:
            messaged = (
                await self.db.execute(
                    text(
                        """
                        SELECT COUNT(DISTINCT session_id) AS c
                        FROM runs
                        WHERE agent_id = :agent_id
                          AND created_at >= :start_utc AND created_at < :end_utc
                        """
                    ),
                    {"agent_id": self.agent_id, "start_utc": period.start_utc, "end_utc": period.end_utc},
                )
            ).scalar() or 0

            replied = (
                await self.db.execute(
                    text(
                        """
                        SELECT COUNT(DISTINCT session_id) AS c
                        FROM runs
                        WHERE agent_id = :agent_id
                          AND created_at >= :start_utc AND created_at < :end_utc
                          AND status = 'succeeded'
                          AND output_message IS NOT NULL AND length(output_message) > 0
                        """
                    ),
                    {"agent_id": self.agent_id, "start_utc": period.start_utc, "end_utc": period.end_utc},
                )
            ).scalar() or 0

            booked = (
                await self.db.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM sqns_visits
                        WHERE agent_id = :agent_id
                          AND visit_datetime >= :start_utc AND visit_datetime < :end_utc
                          AND deleted = false
                        """
                    ),
                    {"agent_id": self.agent_id, "start_utc": period.start_utc, "end_utc": period.end_utc},
                )
            ).scalar() or 0

            arrived = (
                await self.db.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM sqns_visits
                        WHERE agent_id = :agent_id
                          AND visit_datetime >= :start_utc AND visit_datetime < :end_utc
                          AND deleted = false
                          AND attendance IS NOT NULL AND attendance > 0
                        """
                    ),
                    {"agent_id": self.agent_id, "start_utc": period.start_utc, "end_utc": period.end_utc},
                )
            ).scalar() or 0

            paid = (
                await self.db.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM sqns_payments
                        WHERE agent_id = :agent_id
                          AND payment_date >= :start_utc AND payment_date < :end_utc
                          AND amount IS NOT NULL AND amount > 0
                        """
                    ),
                    {"agent_id": self.agent_id, "start_utc": period.start_utc, "end_utc": period.end_utc},
                )
            ).scalar() or 0

            repeated = (
                await self.db.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM sqns_visits
                        WHERE agent_id = :agent_id
                          AND visit_datetime >= :start_utc AND visit_datetime < :end_utc
                          AND deleted = false
                          AND COALESCE(is_primary_visit, true) = false
                        """
                    ),
                    {"agent_id": self.agent_id, "start_utc": period.start_utc, "end_utc": period.end_utc},
                )
            ).scalar() or 0
        except Exception:
            logger.exception("funnel_query_failed")
            messaged = replied = booked = arrived = paid = repeated = 0

        stages = [
            FunnelStage(key="messaged", label="Написал в чат", value=int(messaged)),
            FunnelStage(key="replied", label="Бот ответил", value=int(replied)),
            FunnelStage(key="booked", label="Записан", value=int(booked)),
            FunnelStage(key="arrived", label="Дошёл", value=int(arrived)),
            FunnelStage(key="paid", label="Оплатил", value=int(paid)),
            FunnelStage(key="repeated", label="Повторная запись", value=int(repeated)),
        ]
        return FunnelResponse(
            period_start=period.start_local,
            period_end=period.end_local_exclusive,
            timezone=period.timezone_name,
            stages=stages,
        )

    async def _runs_kpi(self, period: AnalyticsPeriod) -> BotRunsKpi:
        try:
            row = (
                await self.db.execute(
                    text(
                        """
                        SELECT
                          COUNT(*) AS runs_total,
                          COUNT(*) FILTER (WHERE status = 'succeeded') AS success,
                          COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                          COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                          COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                          COALESCE(SUM(cost_usd), 0) AS cost_usd,
                          COALESCE(SUM(cost_rub), 0) AS cost_rub
                        FROM runs
                        WHERE agent_id = :agent_id
                          AND created_at >= :start_utc AND created_at < :end_utc
                        """
                    ),
                    {"agent_id": self.agent_id, "start_utc": period.start_utc, "end_utc": period.end_utc},
                )
            ).mappings().one()

            total = int(row["runs_total"] or 0)
            success = int(row["success"] or 0)

            avg_dur = (
                await self.db.execute(
                    text(
                        """
                        SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) * 1000), 0) AS avg_ms
                        FROM runs
                        WHERE agent_id = :agent_id
                          AND created_at >= :start_utc AND created_at < :end_utc
                          AND status IN ('succeeded', 'failed')
                        """
                    ),
                    {"agent_id": self.agent_id, "start_utc": period.start_utc, "end_utc": period.end_utc},
                )
            ).scalar() or 0
        except Exception:
            logger.exception("runs_kpi_query_failed")
            return BotRunsKpi()

        return BotRunsKpi(
            runs_total=total,
            success_pct=round((success / total) * 100.0, 1) if total else 0.0,
            failed_total=int(row["failed"] or 0),
            avg_duration_ms=float(avg_dur or 0),
            prompt_tokens_total=int(row["prompt_tokens"] or 0),
            completion_tokens_total=int(row["completion_tokens"] or 0),
            cost_usd_total=float(row["cost_usd"] or 0),
            cost_rub_total=float(row["cost_rub"] or 0),
        )

    async def _tool_stats(self, period: AnalyticsPeriod) -> list[BotToolStat]:
        try:
            rows = (
                await self.db.execute(
                    text(
                        """
                        SELECT
                          tool_name,
                          COUNT(*) AS calls_total,
                          COUNT(*) FILTER (WHERE status = 'error') AS error_count,
                          COALESCE(AVG(duration_ms), 0) AS avg_ms,
                          COALESCE(percentile_disc(0.5) WITHIN GROUP (ORDER BY duration_ms), 0) AS p50_ms,
                          COALESCE(percentile_disc(0.95) WITHIN GROUP (ORDER BY duration_ms), 0) AS p95_ms
                        FROM tool_call_logs
                        WHERE agent_id = :agent_id
                          AND invoked_at >= :start_utc AND invoked_at < :end_utc
                        GROUP BY tool_name
                        ORDER BY calls_total DESC
                        LIMIT 20
                        """
                    ),
                    {"agent_id": self.agent_id, "start_utc": period.start_utc, "end_utc": period.end_utc},
                )
            ).mappings().all()
        except Exception:
            logger.exception("tool_stats_query_failed")
            return []

        out: list[BotToolStat] = []
        for r in rows:
            calls = int(r["calls_total"] or 0)
            errors = int(r["error_count"] or 0)
            out.append(
                BotToolStat(
                    tool_name=r["tool_name"],
                    calls_total=calls,
                    error_count=errors,
                    error_pct=round((errors / calls) * 100.0, 1) if calls else 0.0,
                    p50_ms=float(r["p50_ms"] or 0),
                    p95_ms=float(r["p95_ms"] or 0),
                    avg_ms=float(r["avg_ms"] or 0),
                )
            )
        return out

    async def _dialog_quality(self, period: AnalyticsPeriod) -> BotDialogQuality:
        try:
            row = (
                await self.db.execute(
                    text(
                        """
                        SELECT
                          COUNT(*) AS dialogs_total,
                          COUNT(*) FILTER (WHERE last_manager_message_at IS NOT NULL) AS with_manager,
                          COUNT(*) FILTER (WHERE status = 'paused') AS paused,
                          COUNT(*) FILTER (WHERE status = 'disabled') AS disabled
                        FROM dialog_states
                        WHERE agent_id = :agent_id
                          AND (
                            last_user_message_at >= :start_utc OR
                            last_manager_message_at >= :start_utc
                          )
                        """
                    ),
                    {"agent_id": self.agent_id, "start_utc": period.start_utc},
                )
            ).mappings().one()

            avg_msgs = (
                await self.db.execute(
                    text(
                        """
                        SELECT COALESCE(AVG(c), 0) FROM (
                          SELECT COUNT(*) AS c
                          FROM session_messages sm
                          JOIN runs r ON r.id = sm.run_id
                          WHERE r.agent_id = :agent_id
                            AND sm.created_at >= :start_utc AND sm.created_at < :end_utc
                          GROUP BY sm.session_id
                        ) t
                        """
                    ),
                    {"agent_id": self.agent_id, "start_utc": period.start_utc, "end_utc": period.end_utc},
                )
            ).scalar() or 0
        except Exception:
            logger.exception("dialog_quality_query_failed")
            return BotDialogQuality()

        total = int(row["dialogs_total"] or 0)
        with_manager = int(row["with_manager"] or 0)
        return BotDialogQuality(
            dialogs_total=total,
            dialogs_with_manager=with_manager,
            dialogs_paused=int(row["paused"] or 0),
            dialogs_disabled=int(row["disabled"] or 0),
            autonomy_pct=round(((total - with_manager) / total) * 100.0, 1) if total else 0.0,
            avg_messages_per_dialog=round(float(avg_msgs), 1),
        )

    async def _budget(self, period: AnalyticsPeriod) -> BotBudget:
        try:
            balance = (
                await self.db.execute(
                    text(
                        """
                        SELECT initial_balance_usd, spent_usd
                        FROM tenant_balances
                        WHERE tenant_id = :tenant_id
                        LIMIT 1
                        """
                    ),
                    {"tenant_id": self.tenant_id},
                )
            ).mappings().first()
        except Exception:
            balance = None

        if balance is None:
            return BotBudget()

        initial = float(balance["initial_balance_usd"] or 0)
        spent = float(balance["spent_usd"] or 0)
        remaining = max(initial - spent, 0.0)

        try:
            now = datetime.utcnow().replace(tzinfo=period.start_utc.tzinfo)
            since = now - timedelta(days=14)
            last_14 = (
                await self.db.execute(
                    text(
                        """
                        SELECT COALESCE(SUM(cost_usd), 0)
                        FROM runs
                        WHERE tenant_id = :tenant_id
                          AND created_at >= :since
                        """
                    ),
                    {"tenant_id": self.tenant_id, "since": since},
                )
            ).scalar() or 0
        except Exception:
            last_14 = 0

        last_14 = float(last_14)
        burn_per_day = round(last_14 / 14.0, 4)
        days_to_zero = round(remaining / burn_per_day, 1) if burn_per_day > 0 else None

        return BotBudget(
            initial_balance_usd=initial,
            spent_usd=spent,
            remaining_usd=remaining,
            spent_pct=round((spent / initial) * 100.0, 1) if initial > 0 else 0.0,
            burn_rate_usd_per_day=burn_per_day,
            days_to_zero=days_to_zero,
            last_14d_usd=round(last_14, 4),
        )
