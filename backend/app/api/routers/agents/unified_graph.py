"""Корпус и индексация Microsoft GraphRAG (webhook или локальный ``graphrag index``). Превью — опционально из output/."""

from __future__ import annotations

from uuid import UUID

from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.agents.deps import get_agent_or_404
from app.api.deps import require_scope
from app.core.config import get_settings
from app.db.models.unified_graph_rebuild_job import UnifiedGraphRebuildJob
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.services.agent_unified_graph import (
    compute_node_embeddings,
    enrich_semantic_relations,
    load_unified_graph_preview,
    materialize_unified_graph,
)
from app.services.graphrag_export.graph_preview_ask import (
    SUPPORTED_METHODS,
    answer_graph_preview_question,
)
from app.services.runtime.microsoft_graphrag_neo4j_sync import (
    build_microsoft_graphrag_sync_plan,
    read_microsoft_graphrag_neo4j_counts,
    sync_microsoft_graphrag_workspace_to_neo4j,
)
from app.services.unified_graph_rebuild_jobs import (
    create_unified_graph_rebuild_job,
    get_unified_graph_rebuild_job,
    get_latest_unified_graph_rebuild_job,
    run_unified_graph_rebuild_job_in_background,
)

router = APIRouter()


class UnifiedGraphAskBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    method: Literal["naive", "basic", "local", "global", "drift"] = Field(
        default="naive",
        description="Режим поиска: naive (превью+LLM), либо graphrag query --method basic|local|global|drift.",
    )


class UnifiedGraphRebuildBody(BaseModel):
    active_sqns_only: bool = Field(default=True, description="Фильтр только для CRM-сотрудников в корпусе.")


class UnifiedGraphNeo4jSyncBody(BaseModel):
    dry_run: bool = Field(default=True, description="Только показать план синка, не писать в Neo4j.")


def _rebuild_job_payload(job: UnifiedGraphRebuildJob) -> dict[str, object]:
    return {
        "id": str(job.id),
        "status": str(job.status),
        "stage": str(job.stage),
        "progress_pct": int(job.progress_pct),
        "active_sqns_only": bool(job.active_sqns_only),
        "message": job.message,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


@router.post("/rebuild", status_code=status.HTTP_202_ACCEPTED)
async def trigger_graphrag_reindex(
    agent_id: UUID,
    body: UnifiedGraphRebuildBody | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, object]:
    """Запустить rebuild Microsoft GraphRAG в фоне и сразу вернуть persisted job."""
    agent = await get_agent_or_404(agent_id, db, user)
    active_sqns_only = body.active_sqns_only if body is not None else True
    job, created_new = await create_unified_graph_rebuild_job(
        db,
        tenant_id=user.tenant_id,
        agent=agent,
        active_sqns_only=active_sqns_only,
        created_by_user_id=user.user_id,
    )
    if created_new:
        run_unified_graph_rebuild_job_in_background(job.id)
    return {
        "status": "accepted",
        "created_new": created_new,
        "job": _rebuild_job_payload(job),
        "message": (
            "Пересборка поставлена в очередь."
            if created_new
            else "Пересборка уже выполняется; возвращён текущий активный job."
        ),
    }


@router.get("/rebuild-status")
async def get_unified_graph_rebuild_status(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, object]:
    await get_agent_or_404(agent_id, db, user)
    job = await get_latest_unified_graph_rebuild_job(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
    )
    if job is None:
        return {
            "status": "idle",
            "job": None,
        }
    return {
        "status": "active" if job.status in {"queued", "running"} else "idle",
        "job": _rebuild_job_payload(job),
    }


@router.get("/rebuild-jobs/{job_id}")
async def get_unified_graph_rebuild_job_status(
    agent_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, object]:
    await get_agent_or_404(agent_id, db, user)
    job = await get_unified_graph_rebuild_job(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        job_id=job_id,
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rebuild job not found")
    return {
        "status": "active" if job.status in {"queued", "running"} else "idle",
        "job": _rebuild_job_payload(job),
    }


@router.post("/materialize", status_code=status.HTTP_200_OK)
async def post_unified_graph_materialize(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, object]:
    """Быстрая пересборка: structured + embeddings + semantic. Без GraphRAG-индексации."""
    await get_agent_or_404(agent_id, db, user)
    mat = await materialize_unified_graph(
        db, tenant_id=user.tenant_id, agent_id=agent_id
    )
    emb = await compute_node_embeddings(
        db, tenant_id=user.tenant_id, agent_id=agent_id
    )
    enrich = await enrich_semantic_relations(
        db, tenant_id=user.tenant_id, agent_id=agent_id
    )
    return {
        "status": "ok",
        "structured": {
            "nodes": mat.nodes,
            "relations": mat.relations,
            "by_type": mat.by_type,
        },
        "embeddings": {
            "computed": emb.computed,
            "skipped": emb.skipped,
            "failed": emb.failed,
        },
        "semantic": {
            "relations": enrich.relations,
            "by_relation_type": enrich.by_relation_type,
        },
    }


@router.get("/preview")
async def get_unified_graph_preview(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, object]:
    """Превью узлов и рёбер из таблиц agent_unified_graph_*.

    Источник — структурный материализатор (specialists/services/categories/...).
    LLM-извлечения через GraphRAG больше не попадают в визуализацию;
    GraphRAG используется отдельно в query-tool для текстового семантического поиска.
    """
    await get_agent_or_404(agent_id, db, user)
    payload = await load_unified_graph_preview(db, agent_id=agent_id)
    return {
        "tenant_id": str(user.tenant_id),
        "agent_id": str(agent_id),
        **payload,
    }


@router.post("/ask")
async def post_unified_graph_ask(
    agent_id: UUID,
    body: UnifiedGraphAskBody,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, object]:
    """
    Вопрос по графу с переключением режима поиска.

    Режимы:
    - ``naive`` — превью (head N узлов) + LLM, без эмбеддингов. Самый быстрый.
    - ``basic`` — векторный поиск по text_units (graphrag query --method basic).
    - ``local`` — entity-centric поиск (graphrag query --method local).
    - ``global`` — map-reduce по community reports (graphrag query --method global).
    - ``drift`` — local + community context (graphrag query --method drift).
    """
    agent = await get_agent_or_404(agent_id, db, user)
    settings = get_settings()
    result = await answer_graph_preview_question(
        db=db,
        agent=agent,
        settings=settings,
        tenant_id=user.tenant_id,
        question=body.question,
        method=body.method,
    )
    return {
        "answer": str(result.get("answer") or ""),
        "method": str(result.get("method") or body.method),
        "used_nodes": int(result.get("used_nodes") or 0),
        "used_relations": int(result.get("used_relations") or 0),
        "total_nodes": int(result.get("total_nodes") or 0),
        "total_relations": int(result.get("total_relations") or 0),
        "system_prompt": result.get("system_prompt"),
        "user_prompt": result.get("user_prompt"),
        "command": result.get("command"),
        "latency_ms": result.get("latency_ms"),
        "stderr_tail": result.get("stderr_tail"),
        "prompt_templates": result.get("prompt_templates") or [],
        "supported_methods": list(SUPPORTED_METHODS),
    }


@router.get("/neo4j/status")
async def get_unified_graph_neo4j_status(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, object]:
    agent = await get_agent_or_404(agent_id, db, user)
    settings = get_settings()
    plan = await build_microsoft_graphrag_sync_plan(
        settings=settings,
        agent=agent,
        tenant_id=user.tenant_id,
    )
    neo4j_counts = read_microsoft_graphrag_neo4j_counts(
        tenant_id=user.tenant_id,
        agent_id=agent_id,
    )
    return {
        "status": "ok",
        "workspace": plan,
        "neo4j": neo4j_counts,
    }


@router.post("/neo4j/sync")
async def post_unified_graph_neo4j_sync(
    agent_id: UUID,
    body: UnifiedGraphNeo4jSyncBody | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, object]:
    agent = await get_agent_or_404(agent_id, db, user)
    settings = get_settings()
    dry_run = True if body is None else bool(body.dry_run)
    if dry_run:
        plan = await build_microsoft_graphrag_sync_plan(
            settings=settings,
            agent=agent,
            tenant_id=user.tenant_id,
        )
        return {
            "status": "ok",
            "dry_run": True,
            "plan": plan,
        }

    ok, message = await sync_microsoft_graphrag_workspace_to_neo4j(
        settings=settings,
        agent=agent,
        tenant_id=user.tenant_id,
    )
    return {
        "dry_run": False,
        "status": "ok" if ok else "error",
        "message": message,
    }
