from __future__ import annotations

from collections import defaultdict
import copy
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import cast, func, select, Text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.core.config import get_settings
from app.db.models.script_flow_graph_community import ScriptFlowGraphCommunity
from app.db.models.script_flow_graph_diagnostic import ScriptFlowGraphDiagnostic
from app.db.models.script_flow_graph_node import ScriptFlowGraphNode
from app.db.models.script_flow_graph_relation import ScriptFlowGraphRelation
from app.db.models.script_flow import ScriptFlow
from app.db.models.script_flow_version import ScriptFlowVersion
from app.db.models.tool_call_log import ToolCallLog
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.script_flow_definition import validate_flow_definition
from app.services.script_flow_compiler import compile_script_flow_to_text
from app.services.script_flow_graphrag_compiler import compile_script_flow_graphrag_payload
from app.services.script_flow_graphrag_schema import ScriptFlowGraphPreview
from app.services.runtime.script_flow_graphrag_neo4j_read import (
    load_script_flow_graphrag_preview_from_neo4j,
)
from app.services.script_flow_sqns_profiles import build_sqns_profile_lookup
from app.services.tenant_llm_config import get_decrypted_api_key

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
    definition_version: int
    flow_metadata: dict[str, Any]
    flow_definition: dict[str, Any]
    compiled_text: str | None
    index_status: str
    index_error: str | None
    last_indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    index_progress: int | None = None
    index_retry_count: int | None = None


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


class CompileDraftBody(BaseModel):
    """Черновая компиляция с телом (sandbox / превью без сохранения)."""

    flow_definition: dict[str, Any] = {}
    flow_metadata: dict[str, Any] = {}


class GraphPreviewDraftBody(BaseModel):
    flow_definition: dict[str, Any] = {}
    flow_metadata: dict[str, Any] = {}


_COMPILE_DRAFT_CACHE: dict[str, tuple[float, dict[str, str | None]]] = {}
_COMPILE_DRAFT_TTL_SEC = 300.0


def _compile_draft_cache_get(key: str) -> dict[str, str | None] | None:
    hit = _COMPILE_DRAFT_CACHE.get(key)
    if not hit:
        return None
    ts, payload = hit
    if time.monotonic() - ts > _COMPILE_DRAFT_TTL_SEC:
        _COMPILE_DRAFT_CACHE.pop(key, None)
        return None
    return payload


def _compile_draft_cache_store(key: str, payload: dict[str, str | None]) -> None:
    _COMPILE_DRAFT_CACHE[key] = (time.monotonic(), payload)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _coerce_flow_definition(fd: dict[str, Any]) -> dict[str, Any]:
    try:
        return validate_flow_definition(fd)
    except (PydanticValidationError, ValueError, TypeError) as exc:
        raise _api_error(
            "invalid_flow_definition",
            str(exc),
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc


def _graph_preview_from_rows(
    *,
    flow: ScriptFlow,
    nodes: list[ScriptFlowGraphNode],
    relations: list[ScriptFlowGraphRelation],
    communities: list[ScriptFlowGraphCommunity],
    diagnostic: ScriptFlowGraphDiagnostic | None = None,
) -> ScriptFlowGraphPreview:
    return ScriptFlowGraphPreview(
        flow_id=flow.id,
        flow_version=int(flow.published_version or 0),
        nodes=[
            {
                "graph_node_id": row.graph_node_id,
                "node_kind": row.node_kind,
                "entity_type": row.entity_type,
                "title": row.title,
                "description": row.description,
                "source_node_ids": row.source_node_ids or [],
                "properties": row.properties or {},
                "community_key": row.community_key,
            }
            for row in nodes
        ],
        relations=[
            {
                "source_graph_node_id": row.source_graph_node_id,
                "target_graph_node_id": row.target_graph_node_id,
                "relation_type": row.relation_type,
                "weight": row.weight,
                "properties": row.properties or {},
            }
            for row in relations
        ],
        communities=[
            {
                "community_key": row.community_key,
                "title": row.title,
                "summary": row.summary,
                "node_ids": row.node_ids or [],
                "properties": row.properties or {},
            }
            for row in communities
        ],
        debug={
            "source": "stored_index",
            "diagnostic": {
                "flow_version": diagnostic.flow_version,
                "extraction_model": diagnostic.extraction_model,
                "summary_model": diagnostic.summary_model,
                "extraction_mode": diagnostic.extraction_mode,
                "llm_ok_nodes": diagnostic.llm_ok_nodes,
                "llm_failed_nodes": diagnostic.llm_failed_nodes,
                "entity_count": diagnostic.entity_count,
                "relation_count": diagnostic.relation_count,
                "community_count": diagnostic.community_count,
                "summary_llm_count": diagnostic.summary_llm_count,
                "summary_fallback_count": diagnostic.summary_fallback_count,
                "raw": diagnostic.debug or {},
            }
            if diagnostic is not None
            else None,
        },
    )


def _normalize_flow_tool_match(raw: Any, *, flow_id: str) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    raw_flow_id = str(raw.get("flow_id") or "").strip()
    if raw_flow_id != flow_id:
        return None
    node_ref = str(
        raw.get("tactic_node_ref")
        or raw.get("node_id")
        or raw.get("node_ref_id")
        or ""
    ).strip()
    if not node_ref:
        return None
    tactic_title = str(raw.get("tactic_title") or raw.get("title") or "").strip()
    return {
        "node_ref": node_ref,
        "tactic_title": tactic_title,
    }


def _summarize_flow_tool_usage_rows(
    rows: list[tuple[datetime, dict[str, Any] | None]],
    *,
    flow_id: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    counts: dict[str, int] = defaultdict(int)
    titles: dict[str, str] = {}
    last_seen_at: dict[str, datetime] = {}

    for invoked_at, payload in rows:
        if not isinstance(payload, dict):
            continue
        matches = payload.get("matches")
        if not isinstance(matches, list) or not matches:
            continue
        top_match: dict[str, str] | None = None
        for raw_match in matches:
            top_match = _normalize_flow_tool_match(raw_match, flow_id=flow_id)
            if top_match:
                break
        if not top_match:
            continue
        node_ref = top_match["node_ref"]
        counts[node_ref] += 1
        if top_match.get("tactic_title") and not titles.get(node_ref):
            titles[node_ref] = top_match["tactic_title"]
        prev_seen = last_seen_at.get(node_ref)
        if prev_seen is None or invoked_at > prev_seen:
            last_seen_at[node_ref] = invoked_at

    by_node_id: dict[str, dict[str, Any]] = {}
    for node_ref, count in counts.items():
        by_node_id[node_ref] = {
            "node_ref": node_ref,
            "tactic_title": titles.get(node_ref) or None,
            "count": count,
            "last_invoked_at": last_seen_at[node_ref].isoformat() if node_ref in last_seen_at else None,
        }

    top_node_refs = sorted(
        by_node_id.values(),
        key=lambda item: (-int(item.get("count") or 0), str(item.get("tactic_title") or item.get("node_ref") or "")),
    )[:5]
    return top_node_refs, by_node_id


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
    fd = _coerce_flow_definition(payload.flow_definition or {})
    flow = ScriptFlow(
        id=uuid4(),
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        name=payload.name,
        internal_note=payload.internal_note,
        flow_metadata=payload.flow_metadata,
        flow_definition=fd,
    )
    db.add(flow)
    await db.commit()
    await db.refresh(flow)
    return ScriptFlowRead.model_validate(flow)


@router.get("/script-flows/kg-coverage", response_model=dict)
async def get_kg_coverage(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Матрица покрытия «Возражения × Услуги» по всем потокам агента.

    Для каждой пары (objection, service) считаем число узлов, которые и
    закрывают это возражение (через `data.kg_links.objection_ids`), и
    относятся к услуге (через `data.service_ids` узла или любого узла
    в том же потоке).
    """
    await get_agent_or_404(agent_id, db, user)

    from app.db.models.agent_kg_entity import AgentKgEntity

    obj_stmt = (
        select(AgentKgEntity)
        .where(
            AgentKgEntity.agent_id == agent_id,
            AgentKgEntity.tenant_id == user.tenant_id,
            AgentKgEntity.entity_type == "objection",
        )
        .order_by(AgentKgEntity.name.asc())
    )
    objections = list((await db.execute(obj_stmt)).scalars().all())

    flows_stmt = select(ScriptFlow).where(
        ScriptFlow.agent_id == agent_id,
        ScriptFlow.tenant_id == user.tenant_id,
    )
    flows = list((await db.execute(flows_stmt)).scalars().all())

    counts: dict[tuple[str, str], int] = {}
    service_ids_seen: set[str] = set()

    for flow in flows:
        fd = flow.flow_definition or {}
        nodes = fd.get("nodes") or []
        if not isinstance(nodes, list):
            continue
        flow_level_services: set[str] = set()
        for n in nodes:
            if not isinstance(n, dict):
                continue
            d = n.get("data") or {}
            if not isinstance(d, dict):
                continue
            for sid in d.get("service_ids") or []:
                if isinstance(sid, str) and sid:
                    flow_level_services.add(sid)

        for n in nodes:
            if not isinstance(n, dict):
                continue
            d = n.get("data") or {}
            if not isinstance(d, dict):
                continue
            links = d.get("kg_links") or {}
            obj_ids = []
            if isinstance(links, dict):
                obj_ids = [x for x in (links.get("objection_ids") or []) if isinstance(x, str)]
            if not obj_ids:
                continue
            node_services = [
                x for x in (d.get("service_ids") or []) if isinstance(x, str)
            ]
            services = set(node_services) or flow_level_services or {"__any__"}
            for oid in obj_ids:
                for sid in services:
                    service_ids_seen.add(sid)
                    key = (oid, sid)
                    counts[key] = counts.get(key, 0) + 1

    return {
        "objections": [
            {"id": str(o.id), "name": o.name, "description": o.description}
            for o in objections
        ],
        "services": sorted(service_ids_seen),
        "cells": [
            {"objection_id": k[0], "service_id": k[1], "tactic_count": v}
            for k, v in counts.items()
        ],
    }


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
    x_definition_version: int | None = Header(None, alias="X-Definition-Version"),
) -> ScriptFlowRead:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    if payload.flow_definition is not None:
        if x_definition_version is not None and x_definition_version != flow.definition_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "definition_version_conflict",
                    "message": "Поток уже изменён в другой вкладке или у другого пользователя. Обновите страницу.",
                    "detail": None,
                    "field_errors": None,
                },
            )
    if payload.name is not None:
        flow.name = payload.name
    if payload.internal_note is not None:
        flow.internal_note = payload.internal_note
    if payload.flow_metadata is not None:
        flow.flow_metadata = payload.flow_metadata
    if payload.flow_definition is not None:
        flow.flow_definition = _coerce_flow_definition(payload.flow_definition)
        flow.definition_version = flow.definition_version + 1
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
    profile_lookup = await build_sqns_profile_lookup(
        db, agent_id=agent_id, flow_definition=flow.flow_definition or {}
    )
    try:
        compiled_text = compile_script_flow_to_text(
            name=flow.name,
            flow_definition=flow.flow_definition,
            flow_metadata=flow.flow_metadata,
            profile_lookup=profile_lookup,
        )
    except Exception as exc:  # noqa: BLE001
        raise _api_error("compile_error", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY) from exc
    return {"compiled_text": compiled_text}


@router.post("/script-flows/{flow_id}/compile-draft")
async def compile_script_flow_draft(
    agent_id: UUID,
    flow_id: UUID,
    body: CompileDraftBody,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, str | None]:
    """Тот же путь компиляции, что и publish/preview, для чернового тела (sandbox)."""
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    fd_valid = _coerce_flow_definition(body.flow_definition or {})
    profile_lookup = await build_sqns_profile_lookup(
        db, agent_id=agent_id, flow_definition=fd_valid,
    )
    meta = body.flow_metadata if isinstance(body.flow_metadata, dict) else {}
    cache_key_src = json.dumps(
        {
            "agent": str(agent_id),
            "flow": str(flow_id),
            "fd": fd_valid,
            "meta": meta,
        },
        sort_keys=True,
        default=str,
    )
    cache_key = hashlib.sha256(cache_key_src.encode()).hexdigest()
    cached = _compile_draft_cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        compiled_text = compile_script_flow_to_text(
            name=flow.name,
            flow_definition=fd_valid,
            flow_metadata=meta,
            profile_lookup=profile_lookup,
        )
    except Exception as exc:  # noqa: BLE001
        raise _api_error("compile_error", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY) from exc
    out = {"compiled_text": compiled_text}
    _compile_draft_cache_store(cache_key, out)
    return out


@router.post("/script-flows/{flow_id}/graphrag-preview-draft", response_model=ScriptFlowGraphPreview)
async def graphrag_preview_draft(
    agent_id: UUID,
    flow_id: UUID,
    body: GraphPreviewDraftBody,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ScriptFlowGraphPreview:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    draft_flow = ScriptFlow(
        id=flow.id,
        tenant_id=flow.tenant_id,
        agent_id=flow.agent_id,
        name=flow.name,
        internal_note=flow.internal_note,
        flow_status=flow.flow_status,
        published_version=flow.published_version,
        indexed_version=flow.indexed_version,
        definition_version=flow.definition_version,
        flow_metadata=body.flow_metadata if isinstance(body.flow_metadata, dict) else {},
        flow_definition=_coerce_flow_definition(body.flow_definition or {}),
        compiled_text=flow.compiled_text,
        index_status=flow.index_status,
        index_error=flow.index_error,
        last_indexed_at=flow.last_indexed_at,
        index_progress=flow.index_progress,
        index_retry_count=flow.index_retry_count,
        index_cancel_requested=flow.index_cancel_requested,
    )
    openai_api_key = await get_decrypted_api_key(db, flow.tenant_id)
    settings = get_settings()
    payload = await compile_script_flow_graphrag_payload(
        draft_flow,
        openai_api_key=openai_api_key,
        extraction_model=settings.script_flow_graphrag_extraction_model,
        summary_model=settings.script_flow_graphrag_summary_model,
    )
    return payload.preview


@router.get("/script-flows/{flow_id}/graphrag-preview", response_model=ScriptFlowGraphPreview)
async def get_graphrag_preview(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ScriptFlowGraphPreview:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)

    neo4j_preview = await load_script_flow_graphrag_preview_from_neo4j(
        tenant_id=flow.tenant_id,
        agent_id=flow.agent_id,
        flow_id=flow.id,
        fallback_flow_version=int(flow.published_version or 0),
    )
    if neo4j_preview is not None:
        return neo4j_preview

    node_rows = list((await db.execute(
        select(ScriptFlowGraphNode)
        .where(ScriptFlowGraphNode.flow_id == flow.id)
        .order_by(ScriptFlowGraphNode.node_kind.asc(), ScriptFlowGraphNode.title.asc())
    )).scalars().all())
    relation_rows = list((await db.execute(
        select(ScriptFlowGraphRelation)
        .where(ScriptFlowGraphRelation.flow_id == flow.id)
        .order_by(ScriptFlowGraphRelation.relation_type.asc())
    )).scalars().all())
    community_rows = list((await db.execute(
        select(ScriptFlowGraphCommunity)
        .where(ScriptFlowGraphCommunity.flow_id == flow.id)
        .order_by(ScriptFlowGraphCommunity.community_key.asc())
    )).scalars().all())
    diagnostic = (await db.execute(
        select(ScriptFlowGraphDiagnostic)
        .where(ScriptFlowGraphDiagnostic.flow_id == flow.id)
        .order_by(ScriptFlowGraphDiagnostic.flow_version.desc())
        .limit(1)
    )).scalar_one_or_none()

    if node_rows or relation_rows or community_rows:
        return _graph_preview_from_rows(
            flow=flow,
            nodes=node_rows,
            relations=relation_rows,
            communities=community_rows,
            diagnostic=diagnostic,
        )

    openai_api_key = await get_decrypted_api_key(db, flow.tenant_id)
    settings = get_settings()
    payload = await compile_script_flow_graphrag_payload(
        flow,
        openai_api_key=openai_api_key,
        extraction_model=settings.script_flow_graphrag_extraction_model,
        summary_model=settings.script_flow_graphrag_summary_model,
    )
    return payload.preview


@router.post("/script-flows/{flow_id}/publish", response_model=dict)
async def publish_script_flow(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    profile_lookup = await build_sqns_profile_lookup(
        db, agent_id=agent_id, flow_definition=flow.flow_definition or {}
    )
    try:
        compiled_text = compile_script_flow_to_text(
            name=flow.name,
            flow_definition=flow.flow_definition,
            flow_metadata=flow.flow_metadata,
            profile_lookup=profile_lookup,
        )
    except Exception as exc:  # noqa: BLE001
        raise _api_error("compile_error", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY) from exc

    flow.flow_status = "published"
    flow.published_version = flow.published_version + 1
    flow.compiled_text = compiled_text
    flow.index_status = "pending"
    meta = copy.deepcopy(flow.flow_metadata or {})
    meta["published_flow_definition"] = copy.deepcopy(flow.flow_definition or {})
    meta["published_snapshot_version"] = flow.published_version
    flow.flow_metadata = meta
    snap = ScriptFlowVersion(
        id=uuid4(),
        flow_id=flow.id,
        tenant_id=flow.tenant_id,
        version=flow.published_version,
        flow_definition=copy.deepcopy(flow.flow_definition or {}),
        flow_metadata=copy.deepcopy(meta),
        compiled_text=compiled_text,
    )
    db.add(snap)
    await db.commit()
    await db.refresh(flow)
    return {
        "id": str(flow.id),
        "flow_status": flow.flow_status,
        "published_version": flow.published_version,
        "index_status": flow.index_status,
    }


@router.post("/script-flows/{flow_id}/unpublish", response_model=dict)
async def unpublish_script_flow(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Снять поток с публикации: переводит статус в draft, освобождает свитч публикации в шапке."""
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    flow.flow_status = "draft"
    flow.index_status = "idle"
    flow.index_error = None
    flow.index_progress = None
    flow.index_retry_count = 0
    await db.commit()
    await db.refresh(flow)
    return {
        "id": str(flow.id),
        "flow_status": flow.flow_status,
        "published_version": flow.published_version,
        "index_status": flow.index_status,
    }


@router.post("/script-flows/{flow_id}/retry-index", response_model=dict)
async def retry_script_flow_index(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Повторная постановка потока в очередь индексации после сбоя."""
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    if flow.flow_status != "published":
        raise _api_error(
            "not_published",
            "Сначала опубликуйте поток",
            status.HTTP_400_BAD_REQUEST,
        )
    flow.index_status = "pending"
    flow.index_error = None
    flow.index_retry_count = 0
    flow.index_progress = None
    await db.commit()
    await db.refresh(flow)
    return {
        "id": str(flow.id),
        "index_status": flow.index_status,
        "published_version": flow.published_version,
    }


@router.post("/script-flows/{flow_id}/cancel-index", response_model=dict)
async def cancel_script_flow_index(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Запросить отмену текущей индексации (воркер проверит флаг между шагами)."""
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    await db.execute(
        update(ScriptFlow)
        .where(ScriptFlow.id == flow.id)
        .values(index_cancel_requested=True)
    )
    await db.commit()
    await db.refresh(flow)
    return {"id": str(flow.id), "index_cancel_requested": True}


class ScriptFlowBackfillReindexBody(BaseModel):
    """Batch reindex request for published script flows."""

    limit: int = 200
    force_all_published: bool = True


@router.post("/script-flows/reindex-published", response_model=dict)
async def reindex_published_script_flows(
    agent_id: UUID,
    body: ScriptFlowBackfillReindexBody,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Queue published flows for reindex/backfill of retrieval embeddings."""
    await get_agent_or_404(agent_id, db, user)

    normalized_limit = max(1, min(int(body.limit or 200), 2000))
    stmt = (
        select(ScriptFlow.id)
        .where(
            ScriptFlow.agent_id == agent_id,
            ScriptFlow.tenant_id == user.tenant_id,
            ScriptFlow.flow_status == "published",
        )
        .order_by(ScriptFlow.updated_at.desc().nulls_last(), ScriptFlow.created_at.desc())
        .limit(normalized_limit)
    )

    if not body.force_all_published:
        stmt = stmt.where(
            (ScriptFlow.index_status != "pending")
            | (ScriptFlow.indexed_version.is_(None))
            | (ScriptFlow.indexed_version < ScriptFlow.published_version)
        )

    flow_ids = [row[0] for row in (await db.execute(stmt)).all()]
    if not flow_ids:
        return {
            "queued": 0,
            "limit": normalized_limit,
            "force_all_published": body.force_all_published,
            "message": "Нет опубликованных потоков для постановки в очередь.",
        }

    await db.execute(
        update(ScriptFlow)
        .where(ScriptFlow.id.in_(flow_ids))
        .values(
            index_status="pending",
            index_error=None,
            index_progress=None,
            index_retry_count=0,
            index_cancel_requested=False,
        )
    )
    await db.commit()

    return {
        "queued": len(flow_ids),
        "limit": normalized_limit,
        "force_all_published": body.force_all_published,
    }


class ScriptFlowVersionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    created_at: datetime


@router.get("/script-flows/{flow_id}/versions", response_model=list[ScriptFlowVersionListItem])
async def list_script_flow_versions(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[ScriptFlowVersionListItem]:
    await get_agent_or_404(agent_id, db, user)
    await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    stmt = (
        select(ScriptFlowVersion)
        .where(
            ScriptFlowVersion.flow_id == flow_id,
            ScriptFlowVersion.tenant_id == user.tenant_id,
        )
        .order_by(ScriptFlowVersion.version.desc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return [ScriptFlowVersionListItem.model_validate(r) for r in rows]


@router.post("/script-flows/{flow_id}/versions/{published_ver}/restore", response_model=ScriptFlowRead)
async def restore_script_flow_version(
    agent_id: UUID,
    flow_id: UUID,
    published_ver: int,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ScriptFlowRead:
    """Восстановить черновик из сохранённого снимка публикации (история версий)."""
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    stmt = select(ScriptFlowVersion).where(
        ScriptFlowVersion.flow_id == flow_id,
        ScriptFlowVersion.tenant_id == user.tenant_id,
        ScriptFlowVersion.version == published_ver,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise _api_error("not_found", "Версия не найдена", status.HTTP_404_NOT_FOUND)
    flow.flow_definition = _coerce_flow_definition(copy.deepcopy(row.flow_definition or {}))
    meta = copy.deepcopy(row.flow_metadata or {})
    flow.flow_metadata = meta
    flow.definition_version = flow.definition_version + 1
    await db.commit()
    await db.refresh(flow)
    return ScriptFlowRead.model_validate(flow)


@router.get("/script-flows/{flow_id}/tool-usage", response_model=dict)
async def script_flow_tool_usage(
    agent_id: UUID,
    flow_id: UUID,
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Приблизительное число вызовов search_script_flows, связанных с этим потоком."""
    await get_agent_or_404(agent_id, db, user)
    await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 90)))
    fid = str(flow_id)
    stmt = (
        select(func.count())
        .select_from(ToolCallLog)
        .where(
            ToolCallLog.agent_id == agent_id,
            ToolCallLog.tenant_id == user.tenant_id,
            ToolCallLog.tool_name == "search_script_flows",
            ToolCallLog.invoked_at >= since,
            cast(ToolCallLog.response_payload, Text).contains(fid),
        )
    )
    total = int((await db.execute(stmt)).scalar_one() or 0)

    day_bucket = func.date_trunc("day", ToolCallLog.invoked_at)
    daily_stmt = (
        select(day_bucket, func.count())
        .select_from(ToolCallLog)
        .where(
            ToolCallLog.agent_id == agent_id,
            ToolCallLog.tenant_id == user.tenant_id,
            ToolCallLog.tool_name == "search_script_flows",
            ToolCallLog.invoked_at >= since,
            cast(ToolCallLog.response_payload, Text).contains(fid),
        )
        .group_by(day_bucket)
        .order_by(day_bucket)
    )
    daily_rows = list((await db.execute(daily_stmt)).all())
    daily_series: list[dict[str, Any]] = []
    for day, cnt in daily_rows:
        ds = day.date().isoformat() if hasattr(day, "date") else str(day)
        daily_series.append({"date": ds, "count": int(cnt or 0)})

    usage_rows_stmt = (
        select(ToolCallLog.invoked_at, ToolCallLog.response_payload)
        .where(
            ToolCallLog.agent_id == agent_id,
            ToolCallLog.tenant_id == user.tenant_id,
            ToolCallLog.tool_name == "search_script_flows",
            ToolCallLog.invoked_at >= since,
            cast(ToolCallLog.response_payload, Text).contains(fid),
        )
        .order_by(ToolCallLog.invoked_at.desc())
    )
    usage_rows = list((await db.execute(usage_rows_stmt)).all())
    top_node_refs, by_node_id = _summarize_flow_tool_usage_rows(usage_rows, flow_id=fid)

    return {
        "flow_id": fid,
        "days": days,
        "approximate_flow_tool_calls": total,
        "daily_series": daily_series,
        "top_node_refs": top_node_refs,
        "by_node_id": by_node_id,
        "disclaimer": (
            "Счётчик по полнотекстовому совпадению id потока в ответе тула; "
            "top_node_refs/by_node_id — по top-1 match из каждого вызова, grouped by tactic node; "
            "daily_series — группировка по UTC-дню."
        ),
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
    """Песочница для эксперта: runtime-имитация того, что увидит LLM.

    Если legacy-RAG включен — использует тот же `rag.aquery` в hybrid-режиме,
    что и tool `search_script_flows`.
    Если legacy-RAG выключен — использует `ScriptFlowRetriever` (pgvector-ready
    fallback по индекс-таблицам).
    """
    await get_agent_or_404(agent_id, db, user)
    query = str(body.get("query") or "").strip()
    if not query:
        raise _api_error("invalid_query", "query is required", status.HTTP_422_UNPROCESSABLE_ENTITY)

    from app.services.runtime.script_flow_tool import (
        agent_has_indexed_flows,
    )
    from app.services.runtime.script_flow_retriever import ScriptFlowRetriever

    settings = get_settings()
    retrieval_engine = (settings.runtime_script_flow_retrieval_engine or "retriever").strip().lower()
    if not await agent_has_indexed_flows(db, agent_id=agent_id, tenant_id=user.tenant_id):
        return {
            "query": query,
            "status": "no_index",
            "message": "Нет ни одного опубликованного и проиндексированного потока.",
            "matches": [],
        }

    retriever = ScriptFlowRetriever(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
    )
    packet = await retriever.build_context_packet(query=query)
    return {
        "query": query,
        "status": "ok",
        "matches": packet.matches,
        "retrieval_engine": "script_flow_retriever",
        "requested_engine": retrieval_engine,
        "debug": packet.debug,
    }


@router.get("/script-flows/{flow_id}/coverage", response_model=dict)
async def get_coverage(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    fd = flow.flow_definition or {}
    schema_ver = int(fd.get("schema_version") or 1) if isinstance(fd, dict) else 1
    nodes: list[dict] = fd.get("nodes") if isinstance(fd.get("nodes"), list) else []
    edges: list[dict] = fd.get("edges") if isinstance(fd.get("edges"), list) else []
    total_nodes = len(nodes)

    condition_nodes = 0
    condition_branches = 0
    searchable_with_good_question = 0

    checks: list[dict] = []

    if total_nodes == 0:
        checks.append(
            {
                "key": "empty_flow",
                "label": "Поток пустой",
                "passed": False,
                "severity": "critical",
                "details": None,
            }
        )

    for n in nodes:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "")
        d = n.get("data") if isinstance(n.get("data"), dict) else {}
        nt = d.get("node_type")

        if nt == "condition":
            condition_nodes += 1
            conds = d.get("conditions")
            if isinstance(conds, list):
                for c in conds:
                    if isinstance(c, dict):
                        if str(c.get("label") or "").strip():
                            condition_branches += 1
                    elif str(c).strip():
                        condition_branches += 1

        if nt in ("expertise", "question") or (schema_ver < 2 and nt == "trigger"):
            gq = str(d.get("good_question") or "").strip()
            if gq:
                searchable_with_good_question += 1

        if nt in ("expertise", "trigger"):
            if schema_ver >= 2 and nt == "trigger":
                cpe = d.get("client_phrase_examples")
                has_phrase = isinstance(cpe, list) and any(str(p).strip() for p in cpe)
            else:
                phrases = d.get("example_phrases")
                has_phrase = isinstance(phrases, list) and any(str(p).strip() for p in phrases)
            if not has_phrase:
                checks.append(
                    {
                        "key": f"no_examples:{nid}",
                        "label": "Нет примеров реплик",
                        "passed": False,
                        "severity": "critical",
                        "details": nid,
                    }
                )

        if nt == "goto":
            tf = str(d.get("target_flow_id") or "").strip()
            if not tf:
                checks.append(
                    {
                        "key": f"goto_no_target:{nid}",
                        "label": "Переход без целевого потока",
                        "passed": False,
                        "severity": "warning",
                        "details": nid,
                    }
                )

        if nt == "business_rule" and d.get("is_catalog_rule") is True:
            if not d.get("entity_id"):
                checks.append(
                    {
                        "key": f"catalog_no_entity:{nid}",
                        "label": "Бизнес-правило каталога без сущности",
                        "passed": False,
                        "severity": "critical",
                        "details": nid,
                    }
                )

        if nt == "expertise":
            links = d.get("kg_links") if isinstance(d.get("kg_links"), dict) else {}
            mot = links.get("motive_ids") if isinstance(links, dict) else None
            arg = links.get("argument_ids") if isinstance(links, dict) else None
            if not (isinstance(mot, list) and mot) and not (isinstance(arg, list) and arg):
                checks.append(
                    {
                        "key": f"no_kg_links:{nid}",
                        "label": "Тактика без мотива или аргумента в KG",
                        "passed": False,
                        "severity": "warning",
                        "details": nid,
                    }
                )

    critical_failed = sum(1 for c in checks if not c.get("passed") and c.get("severity") == "critical")
    warn_failed = sum(1 for c in checks if not c.get("passed") and c.get("severity") == "warning")
    score = max(0, 100 - critical_failed * 15 - warn_failed * 5)

    searchable = 0
    for n in nodes:
        if not isinstance(n, dict):
            continue
        d = n.get("data") if isinstance(n.get("data"), dict) else {}
        nt = d.get("node_type")
        if d.get("is_searchable") is True:
            searchable += 1
        elif d.get("is_searchable") is False:
            continue
        elif nt in ("expertise", "question", "trigger"):
            searchable += 1

    node_issues: dict[str, list[dict[str, Any]]] = {}
    for c in checks:
        if c.get("passed"):
            continue
        det = c.get("details")
        if not isinstance(det, str) or not det.strip():
            continue
        node_issues.setdefault(det, []).append(
            {
                "key": c.get("key"),
                "label": c.get("label"),
                "severity": c.get("severity"),
            }
        )

    return {
        "flow_id": str(flow_id),
        "score": score,
        "checks": checks,
        "node_issues": node_issues,
        "stats": {
            "total_nodes": total_nodes,
            "searchable_nodes": searchable,
            "searchable_with_good_question": searchable_with_good_question,
            "condition_nodes": condition_nodes,
            "condition_branches": condition_branches,
        },
    }
