"""Как агент работал на самом деле: запуски, ошибки, вызовы инструментов.

Снимок конфигурации отвечает на вопрос «что настроено». Этот модуль отвечает
на «что из этого работает»: какая функция ни разу не вызвалась, какой тул
возвращает пустоту, на чём агент падает.

Считаем агрегатами, а не выгрузкой: в промпт уходит два десятка строк, а не
история диалогов. Проценты не выводим — на этих объёмах доля по десятку
запусков это шум, поэтому наружу отдаём абсолютные числа.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent

ACTIVITY_DAYS = 30
# Запуск в статусе running дольше этого — клиент почти наверняка остался без ответа.
STUCK_MINUTES = 15
MAX_ERRORS = 3
MAX_TOOLS = 12

# Диалоги из каналов отличаются от тестовых прогонов префиксом session_id.
# Без этого прогоны оптимизатора и тестового чата считаются живыми клиентами.
CHANNEL_SESSION_RE = "^(telegram|telegram_phone|whatsapp|jivo|max):"

_KPI_SQL = text(
    """
    SELECT
      count(*) AS runs,
      count(*) FILTER (WHERE status = 'failed') AS failed,
      count(*) FILTER (
        WHERE status = 'running'
          AND created_at < now() - make_interval(mins => :stuck_minutes)
      ) AS stuck,
      count(DISTINCT session_id) AS dialogs,
      count(DISTINCT session_id) FILTER (WHERE session_id ~ :channel_re) AS channel_dialogs,
      round(avg(prompt_tokens)) AS avg_prompt,
      round(avg(completion_tokens)) AS avg_completion,
      max(created_at)::date AS last_run
    FROM runs
    WHERE agent_id = :agent_id
      AND tenant_id = :tenant_id
      AND created_at >= now() - make_interval(days => :days)
    """
)

_ERRORS_SQL = text(
    """
    SELECT left(error_message, 110) AS message,
           count(*) AS times,
           max(created_at)::date AS last_seen
    FROM runs
    WHERE agent_id = :agent_id
      AND tenant_id = :tenant_id
      AND status = 'failed'
      AND error_message IS NOT NULL
      AND created_at >= now() - make_interval(days => :days)
    GROUP BY 1
    ORDER BY times DESC
    LIMIT :limit
    """
)

# Мягкий отказ тула лежит внутри response_payload, а не в error_payload:
# error_payload у всех строк равен json null, фильтровать по нему бесполезно.
# Поле status тоже не годится — рантайм пишет туда success всегда.
_TOOLS_SQL = text(
    """
    SELECT tool_name,
           count(*) AS calls,
           count(*) FILTER (
             WHERE coalesce(response_payload ->> 'status', 'ok') <> 'ok'
                OR jsonb_exists(response_payload, 'error')
           ) AS empty_or_error,
           max(invoked_at)::date AS last_call
    FROM tool_call_logs
    WHERE agent_id = :agent_id
      AND tenant_id = :tenant_id
      AND invoked_at >= now() - make_interval(days => :days)
    GROUP BY tool_name
    ORDER BY calls DESC
    LIMIT :limit
    """
)

# Успешный запуск, в котором модель не позвала ни одного инструмента.
# Считаем анти-джойном по tool_call_logs, а не по runs.tools_called: этот
# jsonb лежит в TOAST, и разбор его по всей таблице стоит мегабайты чтений.
_SILENT_RUNS_SQL = text(
    """
    SELECT count(*) AS runs_without_tools
    FROM runs r
    WHERE r.agent_id = :agent_id
      AND r.tenant_id = :tenant_id
      AND r.status = 'succeeded'
      AND r.created_at >= now() - make_interval(days => :days)
      AND NOT EXISTS (SELECT 1 FROM tool_call_logs t WHERE t.run_id = r.id)
    """
)

# Инструменты, подключённые к агенту, но не вызванные ни разу за период.
# У невызванного тула строк в логе нет вообще, поэтому это анти-джойн от
# списка привязок, а не чтение логов.
_UNUSED_TOOLS_SQL = text(
    """
    SELECT t.name
    FROM agent_tool_bindings b
    JOIN tools t ON t.id = b.tool_id
    WHERE b.agent_id = :agent_id
      AND b.tenant_id = :tenant_id
      AND t.is_deleted IS FALSE
      AND NOT EXISTS (
        SELECT 1 FROM tool_call_logs l
        WHERE l.agent_id = b.agent_id
          AND l.tool_name = t.name
          AND l.invoked_at >= now() - make_interval(days => :days)
      )
    ORDER BY t.name
    LIMIT :limit
    """
)


async def build_activity_snapshot(
    db: AsyncSession, *, agent: Agent, days: int = ACTIVITY_DAYS
) -> dict[str, Any]:
    """Агрегат работы агента за период. Только чтение."""
    params = {"agent_id": agent.id, "tenant_id": agent.tenant_id, "days": days}

    kpi_row = (
        await db.execute(
            _KPI_SQL,
            {**params, "stuck_minutes": STUCK_MINUTES, "channel_re": CHANNEL_SESSION_RE},
        )
    ).mappings().first()
    kpi = dict(kpi_row or {})

    if not kpi.get("runs"):
        # Свежий агент. Молчать честнее, чем показывать нули: по нулям слабая
        # модель начинает рассуждать так, будто что-то измерила.
        return {"detectable": False, "days": days}

    errors = [
        dict(row)
        for row in (
            await db.execute(_ERRORS_SQL, {**params, "limit": MAX_ERRORS})
        ).mappings()
    ]
    tools = [
        dict(row)
        for row in (
            await db.execute(_TOOLS_SQL, {**params, "limit": MAX_TOOLS})
        ).mappings()
    ]
    silent = (await db.execute(_SILENT_RUNS_SQL, params)).scalar_one_or_none() or 0
    unused = [
        row[0]
        for row in (await db.execute(_UNUSED_TOOLS_SQL, {**params, "limit": MAX_TOOLS})).all()
    ]

    return {
        "detectable": True,
        "days": days,
        "kpi": kpi,
        "errors": errors,
        "tools": tools,
        "runs_without_tools": int(silent),
        "unused_tools": unused,
    }


def render_activity(activity: dict[str, Any]) -> str:
    """Агрегат в текст для промпта."""
    days = activity.get("days", ACTIVITY_DAYS)
    if not activity.get("detectable"):
        return (
            f"## Как агент работает\n"
            f"За последние {days} дней у агента не было ни одного запуска. "
            "Данных о работе нет — советуй только по настройкам и не делай выводов "
            "о том, как агент отвечает клиентам."
        )

    kpi = activity["kpi"]
    lines = [
        f"## Как агент работает (за {days} дней)",
        f"Запусков: {kpi['runs']}, из них с ошибкой: {kpi['failed']}, "
        f"зависших дольше {STUCK_MINUTES} минут: {kpi['stuck']}",
        f"Диалогов: {kpi['dialogs']}, из них из каналов (не тестовых): {kpi['channel_dialogs']}",
        f"Средний промпт: {kpi['avg_prompt']} токенов, средний ответ: {kpi['avg_completion']}",
        f"Последний запуск: {kpi['last_run']}",
        f"Успешных запусков, где модель не вызвала ни одного инструмента: "
        f"{activity['runs_without_tools']}",
    ]

    lines.append("")
    lines.append("### Ошибки запусков")
    if activity["errors"]:
        lines.extend(
            f"- {error['message']} — {error['times']} раз, последний {error['last_seen']}"
            for error in activity["errors"]
        )
    else:
        lines.append("Ошибок не было.")

    lines.append("")
    lines.append("### Вызовы инструментов")
    if activity["tools"]:
        for tool in activity["tools"]:
            empty = tool["empty_or_error"]
            tail = f", из них пустых или с отказом: {empty}" if empty else ""
            lines.append(
                f"- {tool['tool_name']}: {tool['calls']} вызовов{tail}, "
                f"последний {tool['last_call']}"
            )
    else:
        lines.append("Инструменты не вызывались ни разу.")

    if activity["unused_tools"]:
        lines.append(
            "Подключены, но ни разу не вызывались: " + ", ".join(activity["unused_tools"])
        )

    lines.append("")
    lines.append(
        "Числа абсолютные. Не считай по ним проценты и не делай выводов о доле, "
        "если запусков меньше двадцати — на такой выборке это случайность, а не тенденция."
    )
    return "\n".join(lines)
