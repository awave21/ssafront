from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.direct_question import DirectQuestion
from app.services.direct_questions.retrieval import search_direct_question_candidates
from app.services.direct_questions.safety import sanitize_direct_question_content, split_direct_question_content


async def build_direct_questions_block(
    db: object,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    max_items: int = 80,
    input_message: str | None = None,
    openai_api_key: str | None = None,
) -> str | None:
    """
    Legacy compatibility shim — больше не используется в основном flow.
    Основной механизм: eager_inject_direct_answer.
    """
    return None


async def eager_inject_direct_answer(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    input_message: str,
    openai_api_key: str | None,
    min_match_percent: int = 45,
    rerank: bool = True,
) -> dict[str, Any] | None:
    """
    Pre-retrieval: до запуска LLM ищем подходящий прямой вопрос по embedding.

    Если находим совпадение — возвращаем словарь с контентом для инжекта в контекст.
    LLM получает готовый ответ и тратит только один ход на форматирование.

    Returns None если совпадений нет — тогда агент работает в обычном режиме.
    """
    result = await search_direct_question_candidates(
        db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        query=input_message,
        openai_api_key=openai_api_key,
        limit=3,
        min_match_percent=min_match_percent,
        rerank=rerank,
    )

    chosen_id = result.get("chosen_candidate_id")
    if not chosen_id:
        return None

    stmt = select(DirectQuestion).where(
        DirectQuestion.id == UUID(chosen_id),
        DirectQuestion.tenant_id == tenant_id,
        DirectQuestion.agent_id == agent_id,
        DirectQuestion.is_enabled.is_(True),
    )
    question = (await db.execute(stmt)).scalar_one_or_none()
    if question is None:
        return None

    safe_content = sanitize_direct_question_content(question.content)
    system_instruction, user_content = split_direct_question_content(safe_content)

    return {
        "direct_question_id": str(question.id),
        "title": question.title,
        "content": user_content,
        "system_instruction": system_instruction,
        "interrupt_dialog": bool(question.interrupt_dialog),
        "notify_telegram": bool(question.notify_telegram),
        "followup": question.followup if isinstance(question.followup, dict) else None,
        "relevance": result.get("matched", [{}])[0].get("relevance", 0.0),
        "retrieval_result": result,
    }


def build_injection_context_block(injection: dict[str, Any]) -> str:
    """
    Формирует блок для инжекта в system prompt.

    LLM видит готовый контент и инструкцию — отвечает без вызова тулов.
    """
    lines: list[str] = [
        f"[Verified answer from knowledge base — topic: {injection['title']}]",
        injection["content"],
    ]
    if injection.get("system_instruction"):
        lines.append(f"\nInstruction: {injection['system_instruction']}")
    lines.append(
        "\nUse the above content as the primary source for your answer. "
        "Preserve exact data (addresses, prices, numbers, URLs). "
        "Do not invent details not present in the content."
    )
    return "\n".join(lines)
