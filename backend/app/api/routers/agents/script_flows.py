from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.db.models.script_flow import ScriptFlow
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.services.script_flow_compiler import compile_script_flow_to_text

router = APIRouter()


def _api_error(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"error": code, "message": message, "detail": message, "field_errors": None},
    )


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class ScriptFlowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    name: str
    internal_note: str | None
    flow_status: str
    published_version: int
    indexed_version: int | None
    flow_metadata: dict[str, Any]
    flow_definition: dict[str, Any]
    compiled_text: str | None
    index_status: str
    index_error: str | None
    last_indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class ScriptFlowCreate(BaseModel):
    name: str
    internal_note: str | None = None
    flow_metadata: dict[str, Any] = {}
    flow_definition: dict[str, Any] = {}


class ScriptFlowUpdate(BaseModel):
    name: str | None = None
    internal_note: str | None = None
    flow_metadata: dict[str, Any] | None = None
    flow_definition: dict[str, Any] | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_flow_or_404(
    db: AsyncSession,
    *,
    agent_id: UUID,
    tenant_id: UUID,
    flow_id: UUID,
) -> ScriptFlow:
    stmt = select(ScriptFlow).where(
        ScriptFlow.id == flow_id,
        ScriptFlow.agent_id == agent_id,
        ScriptFlow.tenant_id == tenant_id,
    )
    flow = (await db.execute(stmt)).scalar_one_or_none()
    if flow is None:
        raise _api_error("not_found", "Script flow not found", status.HTTP_404_NOT_FOUND)
    return flow


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/script-flows", response_model=list[ScriptFlowRead])
async def list_script_flows(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[ScriptFlowRead]:
    await get_agent_or_404(agent_id, db, user)
    stmt = (
        select(ScriptFlow)
        .where(ScriptFlow.agent_id == agent_id, ScriptFlow.tenant_id == user.tenant_id)
        .order_by(ScriptFlow.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [ScriptFlowRead.model_validate(r) for r in rows]


@router.post("/script-flows", response_model=ScriptFlowRead, status_code=status.HTTP_201_CREATED)
async def create_script_flow(
    agent_id: UUID,
    payload: ScriptFlowCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ScriptFlowRead:
    await get_agent_or_404(agent_id, db, user)
    flow = ScriptFlow(
        id=uuid4(),
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        name=payload.name,
        internal_note=payload.internal_note,
        flow_metadata=payload.flow_metadata,
        flow_definition=payload.flow_definition,
    )
    db.add(flow)
    await db.commit()
    await db.refresh(flow)
    return ScriptFlowRead.model_validate(flow)


@router.get("/script-flows/{flow_id}", response_model=ScriptFlowRead)
async def get_script_flow(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ScriptFlowRead:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    return ScriptFlowRead.model_validate(flow)


@router.patch("/script-flows/{flow_id}", response_model=ScriptFlowRead)
async def patch_script_flow(
    agent_id: UUID,
    flow_id: UUID,
    payload: ScriptFlowUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ScriptFlowRead:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    if payload.name is not None:
        flow.name = payload.name
    if payload.internal_note is not None:
        flow.internal_note = payload.internal_note
    if payload.flow_metadata is not None:
        flow.flow_metadata = payload.flow_metadata
    if payload.flow_definition is not None:
        flow.flow_definition = payload.flow_definition
    await db.commit()
    await db.refresh(flow)
    return ScriptFlowRead.model_validate(flow)


@router.delete("/script-flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_script_flow(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    await db.delete(flow)
    await db.commit()


@router.get("/script-flows/{flow_id}/preview")
async def preview_script_flow(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, str | None]:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    try:
        compiled_text = compile_script_flow_to_text(
            name=flow.name,
            flow_definition=flow.flow_definition,
            flow_metadata=flow.flow_metadata,
        )
    except Exception as exc:  # noqa: BLE001
        raise _api_error("compile_error", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY) from exc
    return {"compiled_text": compiled_text}


@router.post("/script-flows/{flow_id}/publish", response_model=dict)
async def publish_script_flow(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    try:
        compiled_text = compile_script_flow_to_text(
            name=flow.name,
            flow_definition=flow.flow_definition,
            flow_metadata=flow.flow_metadata,
        )
    except Exception as exc:  # noqa: BLE001
        raise _api_error("compile_error", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY) from exc

    flow.flow_status = "published"
    flow.published_version = flow.published_version + 1
    flow.compiled_text = compiled_text
    flow.index_status = "pending"
    await db.commit()
    await db.refresh(flow)
    return {
        "id": str(flow.id),
        "flow_status": flow.flow_status,
        "published_version": flow.published_version,
        "index_status": flow.index_status,
    }


@router.post("/script-flows/{flow_id}/suggest-keywords", response_model=dict)
async def suggest_keywords(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    meta = flow.flow_metadata or {}
    return {"keywords": meta.get("keyword_hints") or [], "when_relevant": meta.get("when_relevant")}


@router.post("/script-flows/test-search", response_model=dict)
async def test_search(
    agent_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    await get_agent_or_404(agent_id, db, user)
    return {"query": body.get("query", ""), "matches": []}


@router.get("/script-flows/{flow_id}/coverage", response_model=dict)
async def get_coverage(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    nodes: list[dict] = (flow.flow_definition or {}).get("nodes", [])
    total_nodes = len(nodes)
    searchable = sum(
        1 for n in nodes if n.get("data", {}).get("node_type") in ("expertise", "question", "trigger")
    )
    checks: list[dict] = []
    if total_nodes == 0:
        checks.append({"key": "empty_flow", "label": "Поток пустой", "passed": False,
                       "severity": "critical", "details": None})
    score = 100 if not checks else 0
    return {
        "flow_id": str(flow_id),
        "score": score,
        "checks": checks,
        "stats": {
            "total_nodes": total_nodes,
            "searchable_nodes": searchable,
            "searchable_with_good_question": 0,
            "condition_nodes": 0,
            "condition_branches": 0,
        },
    }
