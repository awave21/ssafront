"""Несколько последних диалогов агента — по запросу, а не в каждом промпте.

Читаем из runs: там input_message и output_message лежат готовым текстом.
Разбирать session_messages не нужно — это формат PydanticAI, он в разы толще
и требует парсинга, а нам нужна расшифровка разговора.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.run import Run

MAX_DIALOGS = 5
MAX_TURNS = 10
# Реплики обрезаем: пять диалогов целиком — это уже страница текста в промпте.
MAX_MESSAGE_CHARS = 400

# Диалог из канала начинается с его префикса. Всё остальное — тестовый чат,
# прогоны оптимизатора и вызовы через API.
_CHANNEL_RE = re.compile(r"^(telegram|telegram_phone|whatsapp|jivo|max):")


def _channel_of(session_id: str) -> str | None:
    match = _CHANNEL_RE.match(session_id or "")
    return match.group(1) if match else None


def _shorten(text: str | None) -> str:
    value = (text or "").strip()
    if len(value) <= MAX_MESSAGE_CHARS:
        return value
    return value[:MAX_MESSAGE_CHARS] + "…"


async def load_recent_dialogs(
    db: AsyncSession, *, agent: Agent, limit: int = 3
) -> list[dict[str, Any]]:
    """Последние диалоги, живые из каналов — в первую очередь."""
    limit = max(1, min(limit, MAX_DIALOGS))

    # Берём с запасом: канальные диалоги могут оказаться не самыми свежими,
    # а показать надо в первую очередь их.
    sessions_stmt = (
        select(
            Run.session_id,
            func.max(Run.created_at).label("last_at"),
            func.count().label("turns"),
        )
        .where(Run.agent_id == agent.id, Run.tenant_id == agent.tenant_id)
        .group_by(Run.session_id)
        .order_by(desc("last_at"))
        .limit(limit * 4)
    )
    rows = (await db.execute(sessions_stmt)).all()
    if not rows:
        return []

    ranked = sorted(
        rows,
        key=lambda row: (_channel_of(row.session_id) is not None, row.last_at),
        reverse=True,
    )[:limit]
    session_ids = [row.session_id for row in ranked]

    runs_stmt = (
        select(Run.session_id, Run.created_at, Run.input_message, Run.output_message, Run.status)
        .where(
            Run.agent_id == agent.id,
            Run.tenant_id == agent.tenant_id,
            Run.session_id.in_(session_ids),
        )
        .order_by(Run.session_id, Run.created_at)
    )
    turns_by_session: dict[str, list[dict[str, Any]]] = {}
    for run in (await db.execute(runs_stmt)).all():
        turns_by_session.setdefault(run.session_id, []).append(
            {
                "client": _shorten(run.input_message),
                "agent": _shorten(run.output_message),
                "failed": run.status == "failed",
            }
        )

    dialogs = []
    for row in ranked:
        turns = turns_by_session.get(row.session_id, [])
        dialogs.append(
            {
                "channel": _channel_of(row.session_id),
                "last_at": row.last_at,
                "turns_total": int(row.turns or 0),
                "turns": turns[-MAX_TURNS:],
            }
        )
    return dialogs


def render_dialogs(dialogs: list[dict[str, Any]]) -> str:
    """Диалоги в текст для промпта."""
    if not dialogs:
        return "У агента ещё не было ни одного диалога."

    lines: list[str] = []
    for index, dialog in enumerate(dialogs, start=1):
        source = f"канал {dialog['channel']}" if dialog["channel"] else "тестовый чат"
        when = dialog["last_at"].strftime("%d.%m.%Y") if dialog["last_at"] else "дата неизвестна"
        shown = len(dialog["turns"])
        total = dialog["turns_total"]
        tail = f", показаны последние {shown} из {total}" if total > shown else ""
        lines.append(f"### Диалог {index} ({source}, {when}, реплик {total}{tail})")
        for turn in dialog["turns"]:
            lines.append(f"Клиент: {turn['client'] or '—'}")
            if turn["failed"]:
                lines.append("Агент: (запуск упал с ошибкой, ответа не было)")
            else:
                lines.append(f"Агент: {turn['agent'] or '(пустой ответ)'}")
        lines.append("")
    lines.append(
        "Это выдержки, реплики длиннее 400 символов обрезаны. Суди по ним об ошибках "
        "агента, но не считай их представительной выборкой."
    )
    return "\n".join(lines)
