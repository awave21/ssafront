from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.db.models.knowledge_file import KnowledgeFile
from app.db.models.knowledge_file_chunk import KnowledgeFileChunk
from app.db.models.knowledge_index_job import KnowledgeIndexJob
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.knowledge_file import (
    KnowledgeFileCreate,
    KnowledgeFileIndexStatusRead,
    KnowledgeFileIndexResponse,
    KnowledgeIndexJobStatusRead,
    KnowledgeFileRead,
    KnowledgeFileUpdate,
    KnowledgeVectorTestChunkRead,
    KnowledgeVectorTestRequest,
    KnowledgeVectorTestResponse,
)
from app.services.knowledge_chunking import DEFAULT_CHUNK_OVERLAP_CHARS, DEFAULT_CHUNK_SIZE_CHARS
from app.services.knowledge_file_extractors import extract_text_from_uploaded_bytes
from app.services.knowledge_files import search_indexed_knowledge_files
from app.services.runtime.model_resolver import resolve_openai_client
from app.services.tenant_llm_config import get_decrypted_api_key
from app.services.knowledge_index_jobs import (
    create_index_job,
    run_index_job_in_background,
    schedule_reindex_descendants_under_folder,
)

router = APIRouter()

MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024


def _knowledge_file_read_with_chunks(item: KnowledgeFile, chunks_count: int | None) -> KnowledgeFileRead:
    base = KnowledgeFileRead.model_validate(item)
    if item.type != "file":
        return base.model_copy(update={"chunks_count": None})
    return base.model_copy(update={"chunks_count": int(chunks_count if chunks_count is not None else 0)})


async def _file_chunks_counts_map(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    file_ids: list[UUID],
) -> dict[UUID, int]:
    if not file_ids:
        return {}
    stmt = (
        select(KnowledgeFileChunk.file_id, func.count(KnowledgeFileChunk.id))
        .where(
            KnowledgeFileChunk.tenant_id == tenant_id,
            KnowledgeFileChunk.agent_id == agent_id,
            KnowledgeFileChunk.file_id.in_(file_ids),
        )
        .group_by(KnowledgeFileChunk.file_id)
    )
    rows = (await db.execute(stmt)).all()
    return {fid: int(n) for fid, n in rows}


async def _file_chunk_count(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    file_id: UUID,
) -> int:
    stmt = select(func.count(KnowledgeFileChunk.id)).where(
        KnowledgeFileChunk.tenant_id == tenant_id,
        KnowledgeFileChunk.agent_id == agent_id,
        KnowledgeFileChunk.file_id == file_id,
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def _get_item_or_404(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    item_id: UUID,
) -> KnowledgeFile:
    stmt = select(KnowledgeFile).where(
        KnowledgeFile.id == item_id,
        KnowledgeFile.tenant_id == tenant_id,
        KnowledgeFile.agent_id == agent_id,
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge file not found")
    return item


@router.get("", response_model=list[KnowledgeFileRead])
async def list_knowledge_files(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[KnowledgeFileRead]:
    await get_agent_or_404(agent_id, db, user)
    stmt = (
        select(KnowledgeFile)
        .where(
            KnowledgeFile.tenant_id == user.tenant_id,
            KnowledgeFile.agent_id == agent_id,
        )
        .order_by(KnowledgeFile.parent_id.asc().nullsfirst(), KnowledgeFile.order_index.asc(), KnowledgeFile.created_at.asc())
    )
    items = (await db.execute(stmt)).scalars().all()
    fids = [i.id for i in items if i.type == "file"]
    counts = await _file_chunks_counts_map(
        db, tenant_id=user.tenant_id, agent_id=agent_id, file_ids=fids
    )
    return [
        _knowledge_file_read_with_chunks(row, counts.get(row.id, 0) if row.type == "file" else None)
        for row in items
    ]


@router.post("", response_model=KnowledgeFileRead, status_code=status.HTTP_201_CREATED)
async def create_knowledge_file(
    agent_id: UUID,
    payload: KnowledgeFileCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> KnowledgeFileRead:
    await get_agent_or_404(agent_id, db, user)

    if payload.parent_id:
        parent = await _get_item_or_404(
            db,
            tenant_id=user.tenant_id,
            agent_id=agent_id,
            item_id=payload.parent_id,
        )
        if parent.type != "folder":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="parent_id must point to a folder")

    order_index = payload.order_index
    if order_index is None:
        max_stmt = select(func.max(KnowledgeFile.order_index)).where(
            KnowledgeFile.tenant_id == user.tenant_id,
            KnowledgeFile.agent_id == agent_id,
            KnowledgeFile.parent_id == payload.parent_id,
        )
        max_idx = (await db.execute(max_stmt)).scalar_one_or_none() or 0
        order_index = int(max_idx) + 1

    item = KnowledgeFile(
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        parent_id=payload.parent_id,
        type=payload.type,
        title=payload.title.strip(),
        meta_tags=payload.meta_tags if payload.type == "file" else [],
        content=payload.content if payload.type == "file" else "",
        is_enabled=payload.is_enabled,
        vector_status="not_indexed" if payload.type == "file" else "not_indexed",
        order_index=order_index,
        chunk_size_chars=payload.chunk_size_chars if payload.type == "folder" else None,
        chunk_overlap_chars=payload.chunk_overlap_chars if payload.type == "folder" else None,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _knowledge_file_read_with_chunks(
        item, 0 if item.type == "file" else None
    )


@router.post("/upload", response_model=KnowledgeFileRead, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_file(
    agent_id: UUID,
    file: UploadFile = File(...),
    parent_id: UUID | None = Form(None),
    title: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> KnowledgeFileRead:
    """
    Upload CSV/PDF/DOCX/TXT and create a new `knowledge_files` file node.

    Note: indexing is triggered separately by `POST /{item_id}/index` (existing behavior),
    so UI can reuse the same reindex polling flow.
    """
    await get_agent_or_404(agent_id, db, user)

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {MAX_UPLOAD_SIZE_BYTES // 1024 // 1024} MB)",
        )

    if parent_id:
        parent = await _get_item_or_404(
            db,
            tenant_id=user.tenant_id,
            agent_id=agent_id,
            item_id=parent_id,
        )
        if parent.type != "folder":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="parent_id must point to a folder")

    try:
        extracted_title, extracted_text = extract_text_from_uploaded_bytes(file.filename or "uploaded", raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document extraction dependency is not installed on the server",
        ) from exc
    final_title = (title or extracted_title).strip() or extracted_title

    extracted_text = (extracted_text or "").strip()
    if not extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No extractable text found in document. "
                "If this is a scanned PDF (images only), OCR is not supported — export text from the PDF or use DOCX/CSV/TXT. "
                "Some damaged or non-standard PDFs fail extraction; try re-saving or printing to PDF from a viewer."
            ),
        )

    # order_index: keep same sibling ordering rule as create_knowledge_file
    max_stmt = select(func.max(KnowledgeFile.order_index)).where(
        KnowledgeFile.tenant_id == user.tenant_id,
        KnowledgeFile.agent_id == agent_id,
        KnowledgeFile.parent_id == parent_id,
    )
    max_idx = (await db.execute(max_stmt)).scalar_one_or_none() or 0
    order_index = int(max_idx) + 1

    item = KnowledgeFile(
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        parent_id=parent_id,
        type="file",
        title=final_title,
        meta_tags=[],
        content=extracted_text,
        is_enabled=True,
        vector_status="not_indexed",
        order_index=order_index,
        chunk_size_chars=None,
        chunk_overlap_chars=None,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _knowledge_file_read_with_chunks(item, 0)


@router.post("/vector-test", response_model=KnowledgeVectorTestResponse)
async def knowledge_vector_rag_test(
    agent_id: UUID,
    payload: KnowledgeVectorTestRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> KnowledgeVectorTestResponse:
    """
    Проверка эмбеддингов: векторный поиск по чанкам (как у search_knowledge_files)
    и краткий ответ модели агента только по найденным фрагментам.
    """
    agent = await get_agent_or_404(agent_id, db, user)
    openai_api_key = await get_decrypted_api_key(db, user.tenant_id)
    if not openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="OpenAI API key is not configured for the organization",
        )

    q = payload.query.strip()
    rows = await search_indexed_knowledge_files(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        query=q,
        openai_api_key=openai_api_key,
        limit=payload.limit,
    )

    chunk_reads: list[KnowledgeVectorTestChunkRead] = []
    for i, row in enumerate(rows, start=1):
        content = str(row.get("content") or "")
        excerpt = content[:1200] + ("…" if len(content) > 1200 else "")
        chunk_reads.append(
            KnowledgeVectorTestChunkRead(
                fragment_index=i,
                chunk_id=UUID(str(row["id"])),
                file_id=UUID(str(row["file_id"])),
                chunk_index=row.get("chunk_index"),
                title=str(row.get("title") or ""),
                relevance=float(row.get("relevance") or 0.0),
                excerpt=excerpt,
            )
        )

    if not chunk_reads:
        return KnowledgeVectorTestResponse(
            chunks=[],
            answer=(
                "Векторный поиск не вернул чанков. Проверьте, что файлы в статусе «Индексировано», "
                "в организации задан ключ OpenAI, и формулировка запроса соответствует содержимому."
            ),
        )

    context_parts: list[str] = []
    toc_lines: list[str] = []
    for i, row in enumerate(rows):
        title = str(row.get("title") or "")
        body = str(row.get("content") or "")[:12_000]
        rel = float(row.get("relevance") or 0.0)
        frag_no = i + 1
        context_parts.append(f"### Фрагмент {frag_no} (файл: {title}, релевантность≈{rel:.3f})\n{body}")
        peek = " ".join((body or "").split())[:200]
        if len(body) > 200:
            peek += "…"
        toc_lines.append(f"- **Фрагмент {frag_no}** (rel≈{rel:.3f}, файл: {title}) — начало: «{peek}»")

    bundle = "\n\n".join(context_parts)
    toc_block = (
        "Сводка (номер здесь = тот же, что у заголовка `### Фрагмент N` ниже; в ответе указывай только эти N):\n"
        + "\n".join(toc_lines)
    )
    user_prompt = (
        f"Вопрос (тест RAG):\n{q}\n\n"
        f"{toc_block}\n\n"
        "Ниже полные тексты фрагментов. Ответь кратко, опираясь только на них. "
        "В конце ответа перечисли номера фрагментов (N из «Фрагмент N»), из которых взяты факты.\n\n"
        f"{bundle}"
    )[:120_000]

    bare_model = agent.model.split(":", 1)[1] if ":" in agent.model else agent.model
    client = resolve_openai_client(openai_api_key=openai_api_key)
    try:
        completion = await client.chat.completions.create(
            model=bare_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты помогаешь проверить индексацию базы знаний агента. Отвечай на русском. "
                        "Если во фрагментах нет данных для ответа — так и скажи. "
                        "Важно: номер фрагмента в тексте ответа должен совпадать с заголовком ### Фрагмент N. "
                        "Если факт есть только во «Фрагменте 5», не пиши «фрагмент 1» — это ошибка нумерации. "
                        "Не путай «первый упомянутый факт» с «Фрагмент 1»."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
        )
        choice = completion.choices[0].message.content
        answer = (choice or "").strip() or None
        answer_error = None
    except Exception as exc:
        answer = None
        answer_error = str(exc)

    return KnowledgeVectorTestResponse(chunks=chunk_reads, answer=answer, answer_error=answer_error)


@router.patch("/{item_id}", response_model=KnowledgeFileRead)
async def update_knowledge_file(
    agent_id: UUID,
    item_id: UUID,
    payload: KnowledgeFileUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> KnowledgeFileRead:
    await get_agent_or_404(agent_id, db, user)
    item = await _get_item_or_404(db, tenant_id=user.tenant_id, agent_id=agent_id, item_id=item_id)
    patch_data = payload.model_dump(exclude_unset=True)

    if item.type == "folder" and (
        "chunk_size_chars" in patch_data or "chunk_overlap_chars" in patch_data
    ):
        next_size = (
            payload.chunk_size_chars
            if "chunk_size_chars" in patch_data
            else item.chunk_size_chars
        )
        next_overlap = (
            payload.chunk_overlap_chars
            if "chunk_overlap_chars" in patch_data
            else item.chunk_overlap_chars
        )
        eff_size = next_size if next_size is not None else DEFAULT_CHUNK_SIZE_CHARS
        eff_overlap = next_overlap if next_overlap is not None else DEFAULT_CHUNK_OVERLAP_CHARS
        if eff_overlap >= eff_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="chunk_overlap_chars must be less than chunk_size_chars (effective values)",
            )

    if "parent_id" in patch_data:
        parent_id = patch_data["parent_id"]
        if parent_id == item.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Item cannot be parent of itself")
        if parent_id is not None:
            parent = await _get_item_or_404(
                db,
                tenant_id=user.tenant_id,
                agent_id=agent_id,
                item_id=parent_id,
            )
            if parent.type != "folder":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="parent_id must point to a folder")
        item.parent_id = parent_id

    if "title" in patch_data and payload.title is not None:
        item.title = payload.title.strip()
    if "meta_tags" in patch_data and item.type == "file":
        item.meta_tags = payload.meta_tags or []
    if "content" in patch_data and item.type == "file" and payload.content is not None:
        item.content = payload.content
        item.vector_status = "not_indexed"
        item.embedding = None
        item.index_error = None
        item.indexed_at = None
    if "is_enabled" in patch_data and payload.is_enabled is not None:
        item.is_enabled = payload.is_enabled
    if "order_index" in patch_data and payload.order_index is not None:
        item.order_index = payload.order_index
    if "chunk_size_chars" in patch_data and item.type == "folder":
        item.chunk_size_chars = payload.chunk_size_chars
    if "chunk_overlap_chars" in patch_data and item.type == "folder":
        item.chunk_overlap_chars = payload.chunk_overlap_chars
    if "vector_status" in patch_data and payload.vector_status is not None and item.type == "file":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vector_status is managed by indexing jobs and cannot be patched directly",
        )

    chunk_settings_changed = item.type == "folder" and (
        "chunk_size_chars" in patch_data or "chunk_overlap_chars" in patch_data
    )

    await db.commit()
    await db.refresh(item)

    if chunk_settings_changed:
        await schedule_reindex_descendants_under_folder(
            db,
            tenant_id=user.tenant_id,
            agent_id=agent_id,
            folder_id=item.id,
        )

    if item.type == "file":
        cc = await _file_chunk_count(
            db, tenant_id=user.tenant_id, agent_id=agent_id, file_id=item.id
        )
        return _knowledge_file_read_with_chunks(item, cc)
    return _knowledge_file_read_with_chunks(item, None)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_file(
    agent_id: UUID,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    await get_agent_or_404(agent_id, db, user)
    item = await _get_item_or_404(db, tenant_id=user.tenant_id, agent_id=agent_id, item_id=item_id)
    await db.delete(item)
    await db.commit()


@router.post("/{item_id}/index", response_model=KnowledgeFileIndexResponse)
async def index_knowledge_file(
    agent_id: UUID,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> KnowledgeFileIndexResponse:
    await get_agent_or_404(agent_id, db, user)
    item = await _get_item_or_404(db, tenant_id=user.tenant_id, agent_id=agent_id, item_id=item_id)
    if item.type != "file":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only file items can be indexed")
    job = await create_index_job(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        file=item,
    )
    run_index_job_in_background(job.id)
    return KnowledgeFileIndexResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        file_id=item.id,
        id=item.id,
        vector_status=item.vector_status,
        indexed_at=item.indexed_at,
        error=item.index_error,
    )


@router.get("/index-jobs/{job_id}", response_model=KnowledgeIndexJobStatusRead)
async def get_index_job_status(
    agent_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> KnowledgeIndexJobStatusRead:
    await get_agent_or_404(agent_id, db, user)
    stmt = select(KnowledgeIndexJob).where(
        KnowledgeIndexJob.id == job_id,
        KnowledgeIndexJob.tenant_id == user.tenant_id,
        KnowledgeIndexJob.agent_id == agent_id,
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index job not found")

    file_row = await db.get(KnowledgeFile, job.file_id)
    file_indexed_at = None
    if (
        file_row is not None
        and file_row.tenant_id == user.tenant_id
        and file_row.agent_id == agent_id
    ):
        file_indexed_at = file_row.indexed_at

    return KnowledgeIndexJobStatusRead(
        job_id=job.id,
        file_id=job.file_id,
        status=job.status,
        progress=job.progress,
        stage=job.stage,
        chunks_total=job.chunks_total,
        chunks_done=job.chunks_done,
        started_at=job.started_at,
        finished_at=job.finished_at,
        indexed_at=file_indexed_at,
        error=job.error,
    )


@router.get("/{item_id}/index-status", response_model=KnowledgeFileIndexStatusRead)
async def get_file_index_status(
    agent_id: UUID,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> KnowledgeFileIndexStatusRead:
    await get_agent_or_404(agent_id, db, user)
    item = await _get_item_or_404(db, tenant_id=user.tenant_id, agent_id=agent_id, item_id=item_id)
    if item.type != "file":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only file items have index status")

    job_stmt = (
        select(KnowledgeIndexJob)
        .where(
            KnowledgeIndexJob.tenant_id == user.tenant_id,
            KnowledgeIndexJob.agent_id == agent_id,
            KnowledgeIndexJob.file_id == item.id,
        )
        .order_by(KnowledgeIndexJob.created_at.desc())
        .limit(1)
    )
    latest_job = (await db.execute(job_stmt)).scalar_one_or_none()

    progress = latest_job.progress if latest_job is not None else (100 if item.vector_status == "indexed" else 0)
    chunks_count = await _file_chunk_count(
        db, tenant_id=user.tenant_id, agent_id=agent_id, file_id=item.id
    )
    return KnowledgeFileIndexStatusRead(
        file_id=item.id,
        vector_status=item.vector_status,
        progress=progress,
        chunks_count=chunks_count,
        indexed_at=item.indexed_at,
        job_id=latest_job.id if latest_job is not None else None,
        stage=latest_job.stage if latest_job is not None else None,
        error=item.index_error or (latest_job.error if latest_job is not None else None),
    )
