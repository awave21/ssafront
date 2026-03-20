from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.direct_question import DirectQuestion, DirectQuestionFile
from app.schemas.direct_question import DirectQuestionCreate, DirectQuestionUpdate
from app.services.direct_questions.embedding import create_direct_question_embedding
from app.services.tenant_llm_config import get_decrypted_api_key


async def list_direct_questions(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
) -> list[DirectQuestion]:
    stmt = (
        select(DirectQuestion)
        .options(selectinload(DirectQuestion.files))
        .where(
            DirectQuestion.tenant_id == tenant_id,
            DirectQuestion.agent_id == agent_id,
        )
        .order_by(DirectQuestion.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


async def _embed_search_title(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    search_title: str,
) -> tuple[list[float] | None, str, datetime | None, str | None]:
    openai_api_key = await get_decrypted_api_key(db, tenant_id)
    embedding = await create_direct_question_embedding(
        search_title,
        db=db,
        tenant_id=tenant_id,
        charge_source_type="embedding.direct_question_title",
        openai_api_key=openai_api_key,
    )
    if embedding is None:
        retry_at = datetime.utcnow() + timedelta(minutes=10)
        return None, "pending", retry_at, "embedding unavailable"
    return embedding, "ready", None, None


async def replace_direct_question_files(
    db: AsyncSession,
    *,
    question: DirectQuestion,
    tenant_id: UUID,
    files: list,
) -> None:
    await db.execute(
        delete(DirectQuestionFile).where(DirectQuestionFile.direct_question_id == question.id)
    )
    await db.flush()
    file_rows: list[DirectQuestionFile] = []
    for idx, payload in enumerate(files):
        file_rows.append(
            DirectQuestionFile(
                tenant_id=tenant_id,
                direct_question_id=question.id,
                name=payload.name,
                url=payload.url,
                size=payload.size,
                type=payload.type,
                sort_order=idx,
            )
        )
    if file_rows:
        db.add_all(file_rows)
    await db.flush()


async def create_direct_question(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    payload: DirectQuestionCreate,
) -> DirectQuestion:
    embedding, embedding_status, embedding_retry_at, embedding_error = await _embed_search_title(
        db,
        tenant_id=tenant_id,
        search_title=payload.search_title,
    )

    question = DirectQuestion(
        tenant_id=tenant_id,
        agent_id=agent_id,
        title=payload.title,
        search_title=payload.search_title,
        content=payload.content,
        tags=payload.tags,
        is_enabled=payload.is_enabled,
        interrupt_dialog=payload.interrupt_dialog,
        notify_telegram=payload.notify_telegram,
        followup=payload.followup.model_dump(mode="json") if payload.followup else None,
        embedding=embedding,
        embedding_status=embedding_status,
        embedding_retry_at=embedding_retry_at,
        embedding_error=embedding_error,
    )
    db.add(question)
    await db.flush()
    await replace_direct_question_files(
        db,
        question=question,
        tenant_id=tenant_id,
        files=payload.files,
    )
    await db.commit()
    refreshed = (
        await db.execute(
            select(DirectQuestion)
            .options(selectinload(DirectQuestion.files))
            .where(DirectQuestion.id == question.id)
        )
    ).scalar_one()
    return refreshed


async def update_direct_question(
    db: AsyncSession,
    *,
    question: DirectQuestion,
    tenant_id: UUID,
    payload: DirectQuestionUpdate,
) -> DirectQuestion:
    update_data = payload.model_dump(exclude_unset=True)
    search_title_changed = "search_title" in update_data and update_data["search_title"] != question.search_title

    for key, value in update_data.items():
        if key in {"files", "followup"}:
            continue
        setattr(question, key, value)

    if "followup" in update_data:
        question.followup = payload.followup.model_dump(mode="json") if payload.followup else None

    if search_title_changed:
        embedding, status, retry_at, embedding_error = await _embed_search_title(
            db,
            tenant_id=tenant_id,
            search_title=question.search_title,
        )
        question.embedding = embedding
        question.embedding_status = status
        question.embedding_retry_at = retry_at
        question.embedding_error = embedding_error

    if payload.files is not None:
        await replace_direct_question_files(
            db,
            question=question,
            tenant_id=tenant_id,
            files=payload.files,
        )

    await db.commit()
    refreshed = (
        await db.execute(
            select(DirectQuestion)
            .options(selectinload(DirectQuestion.files))
            .where(DirectQuestion.id == question.id)
        )
    ).scalar_one()
    return refreshed


async def delete_direct_question(db: AsyncSession, *, question: DirectQuestion) -> None:
    await db.delete(question)
    await db.commit()
