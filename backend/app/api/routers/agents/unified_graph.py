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
from app.services.graph.widget_ask import widget_ask
from app.services.runtime.graphrag_neo4j_sync import (
    build_graphrag_sync_plan,
    read_graphrag_neo4j_counts,
    sync_graphrag_workspace_to_neo4j,
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
    method: Literal["naive", "basic", "local", "global", "drift"] | None = Field(
        default=None,
        description="Игнорируется — оставлено для backwards-compat. Всегда используется neo4j_hybrid.",
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
    """Превью графа: то, что видит runtime-агент через HybridGraphRetriever.

    По умолчанию читает Neo4j (`UNIFIED_GRAPH_DATA_SOURCE=neo4j`) — :FlowNode/:GraphNode/:Service/:Specialist.
    При откате (`UNIFIED_GRAPH_DATA_SOURCE=postgres`) — старые таблицы agent_unified_graph_*.
    """
    await get_agent_or_404(agent_id, db, user)
    settings = get_settings()
    if settings.unified_graph_data_source == "postgres":
        payload = await load_unified_graph_preview(db, agent_id=agent_id)
    else:
        from app.services.graph.unified_preview import load_unified_graph_from_neo4j

        payload = await load_unified_graph_from_neo4j(
            agent_id=agent_id,
            tenant_id=user.tenant_id,
        )
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
    """Вопрос к графу через HybridGraphRetriever — тот же путь, что в рантайме агента."""
    agent = await get_agent_or_404(agent_id, db, user)
    result = await widget_ask(
        db=db,
        agent=agent,
        tenant_id=user.tenant_id,
        question=body.question,
    )
    return result


@router.post("/import-parquet")
async def post_import_parquet(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, object]:
    """Одноразовый импорт GraphRAG parquet entities/relationships в Neo4j."""
    import asyncio as _asyncio
    from app.services.graph.parquet_importer import import_graphrag_parquet_to_neo4j
    from app.services.tenant_llm_config import get_decrypted_api_key

    await get_agent_or_404(agent_id, db, user)
    openai_api_key = await get_decrypted_api_key(db, user.tenant_id)

    async def _run() -> None:
        from app.db.session import async_session_factory
        async with async_session_factory() as session:
            await import_graphrag_parquet_to_neo4j(
                tenant_id=user.tenant_id,
                agent_id=agent_id,
                db=session,
                openai_api_key=openai_api_key,
            )

    _asyncio.create_task(_run())
    return {"status": "started", "message": "Импорт запущен в фоне, см. логи для прогресса."}


@router.get("/neo4j/status")
async def get_unified_graph_neo4j_status(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, object]:
    agent = await get_agent_or_404(agent_id, db, user)
    settings = get_settings()
    plan = await build_graphrag_sync_plan(
        settings=settings,
        agent=agent,
        tenant_id=user.tenant_id,
    )
    neo4j_counts = read_graphrag_neo4j_counts(
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
        plan = await build_graphrag_sync_plan(
            settings=settings,
            agent=agent,
            tenant_id=user.tenant_id,
        )
        return {
            "status": "ok",
            "dry_run": True,
            "plan": plan,
        }

    ok, message = await sync_graphrag_workspace_to_neo4j(
        settings=settings,
        agent=agent,
        tenant_id=user.tenant_id,
    )
    return {
        "dry_run": False,
        "status": "ok" if ok else "error",
        "message": message,
    }
