from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.db.models.knowledge_file import KnowledgeFile
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
)
from app.services.knowledge_index_jobs import create_index_job, run_index_job_in_background

router = APIRouter()


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
    return [KnowledgeFileRead.model_validate(item) for item in items]


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
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return KnowledgeFileRead.model_validate(item)


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
    if "vector_status" in patch_data and payload.vector_status is not None and item.type == "file":
        item.vector_status = payload.vector_status

    await db.commit()
    await db.refresh(item)
    return KnowledgeFileRead.model_validate(item)


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
    return KnowledgeFileIndexStatusRead(
        file_id=item.id,
        vector_status=item.vector_status,
        progress=progress,
        job_id=latest_job.id if latest_job is not None else None,
        stage=latest_job.stage if latest_job is not None else None,
        error=item.index_error or (latest_job.error if latest_job is not None else None),
    )
