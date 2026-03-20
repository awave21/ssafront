from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.direct_question import DirectQuestion
from app.services.direct_questions.embedding import create_direct_question_embedding
from app.services.tenant_llm_config import get_decrypted_api_key

logger = structlog.get_logger(__name__)


async def retry_pending_direct_question_embeddings(
    db: AsyncSession,
    *,
    limit: int,
) -> int:
    now = datetime.utcnow()
    stmt = (
        select(DirectQuestion)
        .where(
            DirectQuestion.embedding.is_(None),
            DirectQuestion.embedding_status.in_(("pending", "failed")),
            (DirectQuestion.embedding_retry_at.is_(None) | (DirectQuestion.embedding_retry_at <= now)),
        )
        .order_by(DirectQuestion.created_at.asc())
        .limit(limit)
    )
    questions = (await db.execute(stmt)).scalars().all()
    if not questions:
        return 0

    updated = 0
    for question in questions:
        openai_api_key = await get_decrypted_api_key(db, question.tenant_id)
        embedding = await create_direct_question_embedding(
            question.search_title,
            db=db,
            tenant_id=question.tenant_id,
            charge_source_type="embedding.direct_question_retry",
            charge_source_id=str(question.id),
            openai_api_key=openai_api_key,
        )
        if embedding is None:
            question.embedding_status = "failed"
            question.embedding_retry_at = datetime.utcnow() + timedelta(minutes=10)
            question.embedding_error = "embedding retry failed"
            continue
        question.embedding = embedding
        question.embedding_status = "ready"
        question.embedding_retry_at = None
        question.embedding_error = None
        updated += 1

    await db.commit()
    logger.info("direct_question_embedding_retry_completed", updated=updated, attempted=len(questions))
    return updated
