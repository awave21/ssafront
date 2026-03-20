from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.knowledge_file import KnowledgeFile
from app.db.models.knowledge_index_job import KnowledgeIndexJob
from app.db.session import async_session_factory
from app.services.directory.service import create_embedding
from app.services.tenant_llm_config import get_decrypted_api_key


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
        chunks_total=1,
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

        job.progress = 45
        job.stage = "embedding"
        await db.commit()

        embedding_text = "\n".join(
            part
            for part in [
                file.title.strip(),
                " ".join(file.meta_tags or []),
                content,
            ]
            if part
        )
        embedding = await create_embedding(
            embedding_text,
            openai_api_key=openai_api_key,
            db=db,
            tenant_id=job.tenant_id,
            charge_source_type="embedding.knowledge_index",
            charge_source_id=str(file.id),
            charge_metadata={"agent_id": str(job.agent_id), "file_id": str(file.id)},
        )
        if embedding is None:
            file.vector_status = "failed"
            file.index_error = "embedding generation failed"
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

        file.embedding = embedding
        file.vector_status = "indexed"
        file.indexed_at = datetime.utcnow()
        file.index_error = None
        job.status = "indexed"
        job.progress = 100
        job.stage = "done"
        job.chunks_done = 1
        job.error = None
        job.finished_at = datetime.utcnow()
        await db.commit()
