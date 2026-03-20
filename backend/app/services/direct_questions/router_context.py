from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.direct_question import DirectQuestion


async def build_direct_questions_block(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    max_items: int = 80,
    input_message: str | None = None,
    openai_api_key: str | None = None,
) -> str | None:
    """
    Build a compact intent list for LLM router-style direct questions.

    Весь список (до max_items) передаётся в системный промпт — модель сама
    определяет, какой пункт релевантен запросу пользователя, и вызывает
    get_direct_answer(uuid). Это принципиально: LLM понимает парафразы,
    синонимы и намерение лучше, чем косинусное сходство.

    Параметры input_message и openai_api_key зарезервированы для возможного
    будущего гибридного режима, когда база знаний очень большая (>200 вопросов),
    но сейчас не используются — решение остаётся за моделью.
    """
    stmt = (
        select(DirectQuestion.id, DirectQuestion.search_title)
        .where(
            DirectQuestion.tenant_id == tenant_id,
            DirectQuestion.agent_id == agent_id,
            DirectQuestion.is_enabled.is_(True),
        )
        .order_by(DirectQuestion.created_at.desc())
        .limit(max_items)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return None

    items: list[str] = []
    for row in rows:
        search_title = str(row.search_title or "").strip()
        if not search_title:
            continue
        items.append(f"- {row.id}: {search_title}")
    if not items:
        return None

    return (
        "Knowledge base (call `get_direct_answer` with UUID to retrieve full answer):\n"
        + "\n".join(items)
    )
