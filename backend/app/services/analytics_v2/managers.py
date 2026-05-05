"""KPI per chat operator (manager): overrides, bot disables, response time."""
from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics_v2 import (
    ManagerOverrideEvent,
    ManagerStat,
    ManagersOverviewResponse,
    ManagersTimelineResponse,
)
from app.services.analytics import AnalyticsPeriod

logger = structlog.get_logger(__name__)


_MANAGER_OVERVIEW_SQL = text(
    """
    WITH manager_msgs AS (
      SELECT
        sm.created_at,
        sm.session_id,
        (sm.message ->> 'manager_user_id')::uuid AS user_id
      FROM session_messages sm
      JOIN runs r ON r.id = sm.run_id
      WHERE r.agent_id = :agent_id
        AND sm.created_at >= :start_utc
        AND sm.created_at <  :end_utc
        AND (sm.message ->> 'role') = 'manager'
    ),
    bot_disables AS (
      SELECT
        aus.disabled_at,
        aus.disabled_by_user_id AS user_id
      FROM agent_user_states aus
      WHERE aus.agent_id = :agent_id
        AND aus.is_disabled = true
        AND aus.disabled_at >= :start_utc
        AND aus.disabled_at <  :end_utc
    ),
    paused_dialogs AS (
      SELECT
        ds.last_manager_message_at AS happened_at,
        NULL::uuid AS user_id,
        ds.session_id
      FROM dialog_states ds
      WHERE ds.agent_id = :agent_id
        AND ds.status = 'paused'
        AND ds.last_manager_message_at IS NOT NULL
        AND ds.last_manager_message_at >= :start_utc
        AND ds.last_manager_message_at <  :end_utc
    ),
    aggregates AS (
      SELECT
        u.id AS user_id,
        u.full_name AS full_name,
        u.email AS email,
        (SELECT COUNT(*) FROM manager_msgs mm WHERE mm.user_id = u.id) AS overrides_count,
        (SELECT COUNT(*) FROM bot_disables bd WHERE bd.user_id = u.id) AS bot_disable_count,
        (SELECT MAX(mm.created_at) FROM manager_msgs mm WHERE mm.user_id = u.id) AS last_active_at
      FROM users u
      WHERE u.tenant_id = :tenant_id
        AND u.is_active = true
    )
    SELECT *
    FROM aggregates
    WHERE overrides_count > 0 OR bot_disable_count > 0
    ORDER BY overrides_count DESC, bot_disable_count DESC
    """
)


_TOTAL_PAUSED_SQL = text(
    """
    SELECT COUNT(*) AS c
    FROM dialog_states ds
    WHERE ds.agent_id = :agent_id
      AND ds.last_manager_message_at >= :start_utc
      AND ds.last_manager_message_at <  :end_utc
    """
)


_TIMELINE_SQL = text(
    """
    (
      SELECT
        sm.created_at AS happened_at,
        'manager_message'::text AS event_type,
        sm.session_id,
        (sm.message ->> 'manager_user_id')::uuid AS user_id,
        u.full_name AS full_name,
        SUBSTRING(COALESCE(sm.message ->> 'content', sm.message::text) FROM 1 FOR 140) AS text_preview
      FROM session_messages sm
      JOIN runs r ON r.id = sm.run_id
      LEFT JOIN users u ON u.id = (sm.message ->> 'manager_user_id')::uuid
      WHERE r.agent_id = :agent_id
        AND sm.created_at >= :start_utc
        AND sm.created_at <  :end_utc
        AND (sm.message ->> 'role') = 'manager'
    )
    UNION ALL
    (
      SELECT
        aus.disabled_at AS happened_at,
        'bot_disabled'::text AS event_type,
        aus.platform_user_id AS session_id,
        aus.disabled_by_user_id AS user_id,
        u.full_name AS full_name,
        NULL AS text_preview
      FROM agent_user_states aus
      LEFT JOIN users u ON u.id = aus.disabled_by_user_id
      WHERE aus.agent_id = :agent_id
        AND aus.is_disabled = true
        AND aus.disabled_at >= :start_utc
        AND aus.disabled_at <  :end_utc
    )
    ORDER BY happened_at DESC
    LIMIT 100
    """
)


class ManagersAnalyticsService:
    def __init__(self, db: AsyncSession, agent_id: UUID, tenant_id: UUID):
        self.db = db
        self.agent_id = agent_id
        self.tenant_id = tenant_id

    async def get_overview(self, period: AnalyticsPeriod) -> ManagersOverviewResponse:
        try:
            rows = (
                await self.db.execute(
                    _MANAGER_OVERVIEW_SQL,
                    {
                        "agent_id": self.agent_id,
                        "tenant_id": self.tenant_id,
                        "start_utc": period.start_utc,
                        "end_utc": period.end_utc,
                    },
                )
            ).mappings().all()
        except Exception:
            logger.exception("managers_overview_query_failed")
            rows = []

        items: list[ManagerStat] = []
        for row in rows:
            items.append(
                ManagerStat(
                    user_id=row["user_id"],
                    full_name=row["full_name"] or row["email"] or "—",
                    email=row["email"],
                    overrides_count=int(row["overrides_count"] or 0),
                    bot_disable_count=int(row["bot_disable_count"] or 0),
                    last_active_at=row["last_active_at"],
                )
            )

        try:
            paused = await self.db.execute(
                _TOTAL_PAUSED_SQL,
                {
                    "agent_id": self.agent_id,
                    "start_utc": period.start_utc,
                    "end_utc": period.end_utc,
                },
            )
            paused_total = int(paused.scalar() or 0)
        except Exception:
            paused_total = 0

        return ManagersOverviewResponse(
            period_start=period.start_local,
            period_end=period.end_local_exclusive,
            timezone=period.timezone_name,
            items=items,
            managers_total=len(items),
            overrides_total=sum(i.overrides_count for i in items),
            bot_disable_total=sum(i.bot_disable_count for i in items) + paused_total,
        )

    async def get_timeline(self, period: AnalyticsPeriod) -> ManagersTimelineResponse:
        try:
            rows = (
                await self.db.execute(
                    _TIMELINE_SQL,
                    {
                        "agent_id": self.agent_id,
                        "start_utc": period.start_utc,
                        "end_utc": period.end_utc,
                    },
                )
            ).mappings().all()
        except Exception:
            logger.exception("managers_timeline_query_failed")
            rows = []

        events: list[ManagerOverrideEvent] = []
        for row in rows:
            events.append(
                ManagerOverrideEvent(
                    happened_at=row["happened_at"],
                    event_type=row["event_type"],
                    session_id=row["session_id"],
                    user_id=row["user_id"],
                    full_name=row["full_name"],
                    text_preview=row["text_preview"],
                )
            )

        return ManagersTimelineResponse(
            period_start=period.start_local,
            period_end=period.end_local_exclusive,
            timezone=period.timezone_name,
            events=events,
        )
