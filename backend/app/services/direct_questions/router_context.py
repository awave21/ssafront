from __future__ import annotations

from typing import Any
from uuid import UUID


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
    Legacy compatibility shim — не используется в runtime.

    Прямые вопросы обрабатываются только через тулы search_direct_questions и get_direct_answer.
    """
    return None
