"""Корпус и индексация Microsoft GraphRAG (webhook или локальный ``graphrag index``). Превью — опционально из output/."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.agents.deps import get_agent_or_404
from app.api.deps import require_scope
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.services.graphrag_export.corpus_dispatch import dispatch_microsoft_graphrag_corpus
from app.services.graphrag_export.graph_preview_ask import answer_graph_preview_question
from app.services.graphrag_export.graphrag_preview import (
    agent_graphrag_workspace,
    load_graphrag_preview_from_workspace,
)

router = APIRouter()


class UnifiedGraphAskBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)


class UnifiedGraphRebuildBody(BaseModel):
    active_sqns_only: bool = Field(default=True, description="Фильтр только для CRM-сотрудников в корпусе.")


@router.post("/rebuild")
async def trigger_graphrag_reindex(
    agent_id: UUID,
    body: UnifiedGraphRebuildBody | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, str | bool]:
    """Webhook или локальный ``graphrag index``."""
    agent = await get_agent_or_404(agent_id, db, user)
    settings = get_settings()
    active_sqns_only = body.active_sqns_only if body is not None else True
    ok, msg = await dispatch_microsoft_graphrag_corpus(
        db=db, agent=agent, settings=settings, active_sqns_only=active_sqns_only
    )
    if not ok:
        if (
            "не задан" in msg
            or "Не задан" in msg
            or "not configured" in msg.lower()
            or "OPENAI_API_KEY" in msg
            or "GRAPHRAG_API_KEY" in msg
            or "Нет ключа OpenAI" in msg
            or "организации" in msg
        ):
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=502, detail=msg)
    return {"status": "accepted", "message": msg}


@router.get("/preview")
async def get_unified_graph_preview(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, object]:
    """Превью узлов и рёбер из ``output/*.parquet`` локального workspace GraphRAG."""
    agent = await get_agent_or_404(agent_id, db, user)
    settings = get_settings()
    ws = agent_graphrag_workspace(settings, tenant_id=user.tenant_id, agent=agent)
    if ws is None:
        return {
            "tenant_id": str(user.tenant_id),
            "agent_id": str(agent_id),
            "nodes": [],
            "relations": [],
            "node_count": 0,
            "edge_count": 0,
            "truncated": False,
            "preview_source": "no_workspace",
            "preview_error": None,
            "message": (
                "Превью доступно при локальной индексации: задайте MICROSOFT_GRAPHRAG_WORKSPACE_ROOT "
                "и выполните «Обновить граф». Данные читаются из каталога output/ этого агента."
            ),
        }
    payload = load_graphrag_preview_from_workspace(ws)
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
) -> dict[str, str | int]:
    """
    Вопрос по снимку графа из превью GraphRAG (тот же источник, что и GET /preview).
    Ответ строится моделью OpenAI только на переданном контексте узлов и связей.
    """
    agent = await get_agent_or_404(agent_id, db, user)
    settings = get_settings()
    result = await answer_graph_preview_question(
        db=db,
        agent=agent,
        settings=settings,
        tenant_id=user.tenant_id,
        question=body.question,
    )
    return {
        "answer": str(result["answer"]),
        "used_nodes": int(result["used_nodes"]),
        "used_relations": int(result["used_relations"]),
    }
