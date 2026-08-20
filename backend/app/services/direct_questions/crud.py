from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select, text, update
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


# Сколько символов ответа берём в вектор. Ограничение не про лимит модели
# (у text-embedding-3-small он 8191 токен), а про смысл: длинный ответ
# размывает вектор, и карточка начинает находиться на что угодно.
MAX_EMBEDDING_CONTENT_CHARS = 1500


def _build_embedding_text(title: str, content: str = "") -> str:
    """
    Расширяем заголовок до поискового текста.

    Одно слово ("Адрес", "Цена", "Режим работы") даёт слабый вектор —
    пользователь спрашивает развёрнутыми фразами. Добавляем вопросительную
    форму, чтобы семантически покрыть типичные запросы.

    Содержимое добавляем следом: ответ лежит именно в нём. Пока искали только
    по заголовку, карточка «Оборудование для эпиляции» не находилась ни по
    одному вопросу про саму процедуру — половина смысла карточки в поиске
    не участвовала.
    """
    title_clean = title.strip().rstrip("?.,!")
    parts = [f"{title_clean}. {title_clean}?"]
    body = (content or "").strip()
    if body:
        parts.append(body[:MAX_EMBEDDING_CONTENT_CHARS])
    return "\n".join(parts)


async def _embed_question(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    title: str,
    content: str = "",
) -> tuple[list[float] | None, str, datetime | None, str | None]:
    openai_api_key = await get_decrypted_api_key(db, tenant_id)
    embedding_text = _build_embedding_text(title, content)
    embedding = await create_direct_question_embedding(
        embedding_text,
        db=db,
        tenant_id=tenant_id,
        # Строку источника списания не трогаем, хотя вектор теперь шире:
        # это ключ идемпотентности в балансе, а не описание.
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
    embedding, embedding_status, embedding_retry_at, embedding_error = await _embed_question(
        db,
        tenant_id=tenant_id,
        title=payload.title,
        content=payload.content,
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
    # Содержимое теперь тоже в векторе, значит его правка требует пересчёта.
    content_changed = "content" in update_data and update_data["content"] != question.content

    for key, value in update_data.items():
        if key in {"files", "followup"}:
            continue
        setattr(question, key, value)

    if "followup" in update_data:
        question.followup = payload.followup.model_dump(mode="json") if payload.followup else None

    if title_changed or content_changed:
        embedding, status, retry_at, embedding_error = await _embed_question(
            db,
            tenant_id=tenant_id,
            title=question.title,
            content=question.content,
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

    # Тексты забираем до цикла: списание внутри create_direct_question_embedding
    # коммитит, инстансы протухают, и обращение к полю в середине цикла поднимает
    # ленивую загрузку — а вместе с ней автосброс наполовину присвоенных векторов.
    payloads = [
        (question.id, _build_embedding_text(question.title, question.content))
        for question in questions
    ]

    # Считаем все векторы, ничего не присваивая. Списание за эмбеддинг внутри
    # коммитит, и висящее в сессии присвоение вектора улетело бы в этот чужой
    # коммит на протухших инстансах — цикл падал на второй карточке.
    computed: list[tuple[UUID, list[float]]] = []
    failed = 0
    for question_id, embedding_text in payloads:
        new_embedding = await create_direct_question_embedding(
            embedding_text,
            db=db,
            tenant_id=tenant_id,
            charge_source_type="embedding.direct_question_reembed",
            charge_source_id=str(question_id),
            openai_api_key=openai_api_key,
        )
        if new_embedding is None:
            failed += 1
            continue
        computed.append((question_id, new_embedding))

    # Двойной каст — приём, которым весь этот код обходил конфликт кодека
    # pgvector с типом SQLAlchemy (см. retrieval.py, hybrid_search.py и др.).
    # Сам конфликт устранён в app/db/session.py, но запись оставлена такой:
    # она работает и с кодеком, и без него.
    for question_id, embedding in computed:
        await db.execute(
            text(
                """
                UPDATE direct_questions
                SET embedding = CAST(CAST(:embedding AS text) AS vector),
                    embedding_status = 'ready',
                    embedding_retry_at = NULL,
                    embedding_error = NULL,
                    updated_at = now()
                WHERE id = :question_id
                """
            ),
            {
                "embedding": "[" + ",".join(str(float(x)) for x in embedding) + "]",
                "question_id": question_id,
            },
        )

    await db.commit()
    return {"updated": len(computed), "failed": failed}
