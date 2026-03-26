from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.knowledge_file import KnowledgeFile
from app.db.models.knowledge_index_job import KnowledgeIndexJob
from app.db.models.knowledge_file_chunk import KnowledgeFileChunk
from app.db.session import async_session_factory
from app.services.directory.service import create_embedding
from app.services.knowledge_chunking import (
    DEFAULT_CHUNK_OVERLAP_CHARS,
    DEFAULT_CHUNK_SIZE_CHARS,
    chunk_text_by_chars,
)
from app.services.tenant_llm_config import get_decrypted_api_key

logger = structlog.get_logger(__name__)

MAX_BULK_REINDEX_FILES = 200


async def _resolve_effective_chunking_settings(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
    file: KnowledgeFile,
) -> tuple[int, int]:
    """
    Resolve chunking settings:
    - prefer explicit values on the nearest parent folder
    - fallback to defaults if nothing is configured
    """
    current_parent_id = file.parent_id
    while current_parent_id:
        stmt = (
            select(KnowledgeFile)
            .where(
                KnowledgeFile.id == current_parent_id,
                KnowledgeFile.tenant_id == tenant_id,
                KnowledgeFile.agent_id == agent_id,
                KnowledgeFile.type == "folder",
            )
        )
        folder = (await db.execute(stmt)).scalar_one_or_none()
        if folder is None:
            break

        chunk_size = folder.chunk_size_chars
        chunk_overlap = folder.chunk_overlap_chars
        if chunk_size is not None and chunk_overlap is not None:
            return int(chunk_size), int(chunk_overlap)

        # If only one of them is set, still allow mixing with defaults.
        if chunk_size is not None or chunk_overlap is not None:
            return (
                int(chunk_size) if chunk_size is not None else DEFAULT_CHUNK_SIZE_CHARS,
                int(chunk_overlap) if chunk_overlap is not None else DEFAULT_CHUNK_OVERLAP_CHARS,
            )

        current_parent_id = folder.parent_id

    return DEFAULT_CHUNK_SIZE_CHARS, DEFAULT_CHUNK_OVERLAP_CHARS


async def _descendant_file_ids_under_folder(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    folder_id: UUID,
) -> list[UUID]:
    stmt = select(KnowledgeFile).where(
        KnowledgeFile.tenant_id == tenant_id,
        KnowledgeFile.agent_id == agent_id,
    )
    items = (await db.execute(stmt)).scalars().all()
    by_id = {node.id: node for node in items}

    def file_is_under_folder(file_node: KnowledgeFile) -> bool:
        if file_node.type != "file":
            return False
        cur = file_node.parent_id
        while cur is not None:
            if cur == folder_id:
                return True
            parent = by_id.get(cur)
            if parent is None:
                return False
            cur = parent.parent_id
        return False

    return [node.id for node in items if file_is_under_folder(node)]


async def schedule_reindex_descendants_under_folder(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    folder_id: UUID,
) -> int:
    """
    Queue index jobs for every file with non-empty content under folder_id (recursive).
    Capped to avoid embedding storms; logs when capped.
    """
    ids = await _descendant_file_ids_under_folder(
        db, tenant_id=tenant_id, agent_id=agent_id, folder_id=folder_id
    )
    if len(ids) > MAX_BULK_REINDEX_FILES:
        logger.warning(
            "knowledge_bulk_reindex_capped",
            folder_id=str(folder_id),
            requested=len(ids),
            cap=MAX_BULK_REINDEX_FILES,
        )
        ids = ids[:MAX_BULK_REINDEX_FILES]

    scheduled = 0
    for fid in ids:
        file_row = await db.get(KnowledgeFile, fid)
        if file_row is None or not (file_row.content or "").strip():
            continue
        job = await create_index_job(db, tenant_id=tenant_id, agent_id=agent_id, file=file_row)
        run_index_job_in_background(job.id)
        scheduled += 1
    if scheduled:
        logger.info(
            "knowledge_bulk_reindex_scheduled",
            folder_id=str(folder_id),
            jobs=scheduled,
        )
    return scheduled


async def create_index_job(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    file: KnowledgeFile,
) -> KnowledgeIndexJob:
    file.vector_status = "indexing"
    file.index_error = None

    job = KnowledgeIndexJob(
        tenant_id=tenant_id,
        agent_id=agent_id,
        file_id=file.id,
        status="queued",
        progress=0,
        stage="queued",
        chunks_total=None,
        chunks_done=0,
        started_at=None,
        finished_at=None,
        error=None,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    await db.refresh(file)
    return job


def run_index_job_in_background(job_id: UUID) -> None:
    asyncio.create_task(_process_index_job(job_id))


async def _process_index_job(job_id: UUID) -> None:
    async with async_session_factory() as db:
        job = await db.get(KnowledgeIndexJob, job_id)
        if job is None:
            return

        stmt = select(KnowledgeFile).where(
            KnowledgeFile.id == job.file_id,
            KnowledgeFile.tenant_id == job.tenant_id,
            KnowledgeFile.agent_id == job.agent_id,
        )
        file = (await db.execute(stmt)).scalar_one_or_none()
        if file is None:
            job.status = "failed"
            job.progress = 100
            job.stage = "failed"
            job.error = "file_not_found"
            job.finished_at = datetime.utcnow()
            await db.commit()
            return

        job.status = "indexing"
        job.progress = 10
        job.stage = "preparing"
        job.started_at = datetime.utcnow()
        await db.commit()

        content = (file.content or "").strip()
        if not content:
            file.vector_status = "failed"
            file.index_error = "content is empty"
            file.embedding = None
            file.indexed_at = None
            job.status = "failed"
            job.progress = 100
            job.stage = "failed"
            job.chunks_done = 0
            job.error = file.index_error
            job.finished_at = datetime.utcnow()
            await db.commit()
            return

        openai_api_key = await get_decrypted_api_key(db, job.tenant_id)
        if not openai_api_key:
            file.vector_status = "failed"
            file.index_error = "OpenAI API key is not configured for tenant"
            file.embedding = None
            file.indexed_at = None
            job.status = "failed"
            job.progress = 100
            job.stage = "failed"
            job.chunks_done = 0
            job.error = file.index_error
            job.finished_at = datetime.utcnow()
            await db.commit()
            return

        chunk_size_chars, chunk_overlap_chars = await _resolve_effective_chunking_settings(
            db=db,
            tenant_id=job.tenant_id,
            agent_id=job.agent_id,
            file=file,
        )

        chunks = chunk_text_by_chars(
            content,
            chunk_size_chars=chunk_size_chars,
            chunk_overlap_chars=chunk_overlap_chars,
        )

        if not chunks:
            file.vector_status = "failed"
            file.index_error = "no chunks after chunking"
            file.embedding = None
            file.indexed_at = None
            job.status = "failed"
            job.progress = 100
            job.stage = "failed"
            job.chunks_total = 0
            job.chunks_done = 0
            job.error = file.index_error
            job.finished_at = datetime.utcnow()
            await db.commit()
            return

        # Replace previous chunks for this file (idempotent reindex).
        await db.execute(delete(KnowledgeFileChunk).where(KnowledgeFileChunk.file_id == file.id))
        await db.commit()

        job.chunks_total = len(chunks)
        job.chunks_done = 0
        job.progress = 20
        job.stage = "embedding"
        await db.commit()

        for idx, chunk in enumerate(chunks):
            chunk_embedding_text = "\n".join(
                part
                for part in [
                    file.title.strip(),
                    " ".join(file.meta_tags or []),
                    chunk,
                ]
                if part
            )

            embedding = await create_embedding(
                chunk_embedding_text,
                openai_api_key=openai_api_key,
                db=db,
                tenant_id=job.tenant_id,
                charge_source_type="embedding.knowledge_index_chunk",
                charge_source_id=f"{file.id}:{idx}",
                charge_metadata={"agent_id": str(job.agent_id), "file_id": str(file.id), "chunk_index": idx},
            )

            if embedding is None:
                file.vector_status = "failed"
                file.index_error = "embedding generation failed"
                file.embedding = None
                file.indexed_at = None
                job.status = "failed"
                job.progress = 100
                job.stage = "failed"
                job.error = file.index_error
                job.finished_at = datetime.utcnow()
                job.chunks_done = idx
                await db.commit()
                return

            db.add(
                KnowledgeFileChunk(
                    tenant_id=job.tenant_id,
                    agent_id=job.agent_id,
                    file_id=file.id,
                    chunk_index=idx,
                    chunk_text=chunk,
                    embedding=embedding,
                )
            )

            # Persist progress frequently so UI polling stays responsive.
            job.chunks_done = idx + 1
            job.progress = int((job.chunks_done / job.chunks_total) * 100) if job.chunks_total else 0
            job.stage = "embedding" if job.progress < 100 else "done"
            await db.commit()

        file.vector_status = "indexed"
        file.embedding = None
        file.indexed_at = datetime.utcnow()
        file.index_error = None

        job.status = "indexed"
        job.progress = 100
        job.stage = "done"
        job.error = None
        job.finished_at = datetime.utcnow()
        await db.commit()
