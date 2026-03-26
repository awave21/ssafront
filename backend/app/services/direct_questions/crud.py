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


def _build_embedding_text(title: str) -> str:
    """
    Расширяем заголовок до поискового текста.

    Одно слово ("Адрес", "Цена", "Режим работы") даёт слабый вектор —
    пользователь спрашивает развёрнутыми фразами. Добавляем вопросительную
    форму, чтобы семантически покрыть типичные запросы.
    """
    title_clean = title.strip().rstrip("?.,!")
    return f"{title_clean}. {title_clean}?"


async def _embed_title(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    title: str,
) -> tuple[list[float] | None, str, datetime | None, str | None]:
    openai_api_key = await get_decrypted_api_key(db, tenant_id)
    embedding_text = _build_embedding_text(title)
    embedding = await create_direct_question_embedding(
        embedding_text,
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
    embedding, embedding_status, embedding_retry_at, embedding_error = await _embed_title(
        db,
        tenant_id=tenant_id,
        title=payload.title,
    )

    question = DirectQuestion(
        tenant_id=tenant_id,
        agent_id=agent_id,
        title=payload.title,
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
    title_changed = "title" in update_data and update_data["title"] != question.title

    for key, value in update_data.items():
        if key in {"files", "followup"}:
            continue
        setattr(question, key, value)

    if "followup" in update_data:
        question.followup = payload.followup.model_dump(mode="json") if payload.followup else None

    if title_changed:
        embedding, status, retry_at, embedding_error = await _embed_title(
            db,
            tenant_id=tenant_id,
            title=question.title,
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


async def reembed_agent_direct_questions(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
) -> dict[str, int]:
    """
    Принудительно пересчитывает embeddings для всех активных прямых вопросов агента.

    Полезно после изменения логики построения embedding-текста
    (например, с title → title + title?).

    Возвращает {"updated": N, "failed": M}.
    """
    stmt = select(DirectQuestion).where(
        DirectQuestion.tenant_id == tenant_id,
        DirectQuestion.agent_id == agent_id,
    )
    questions = (await db.execute(stmt)).scalars().all()
    if not questions:
        return {"updated": 0, "failed": 0}

    openai_api_key = await get_decrypted_api_key(db, tenant_id)
    updated = 0
    failed = 0
    for question in questions:
        embedding_text = _build_embedding_text(question.title)
        new_embedding = await create_direct_question_embedding(
            embedding_text,
            db=db,
            tenant_id=tenant_id,
            charge_source_type="embedding.direct_question_reembed",
            charge_source_id=str(question.id),
            openai_api_key=openai_api_key,
        )
        if new_embedding is None:
            failed += 1
            continue
        question.embedding = new_embedding
        question.embedding_status = "ready"
        question.embedding_retry_at = None
        question.embedding_error = None
        updated += 1

    await db.commit()
    return {"updated": updated, "failed": failed}
