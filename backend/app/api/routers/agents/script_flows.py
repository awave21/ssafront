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
from app.services.script_flow_skill_distiller import (
    distill_skill,
    converse_skill,
    converse_skill_stream,
    _sanitize_skill_doc,
)
from sse_starlette.sse import EventSourceResponse
from app.services.script_flow_graphrag_compiler import compile_script_flow_graphrag_payload
from app.services.script_flow_graphrag_schema import ScriptFlowGraphPreview
from app.services.runtime.script_flow_graphrag_neo4j_read import (
    load_script_flow_graphrag_preview_from_neo4j,
)
from app.services.script_flow_sqns_profiles import build_sqns_profile_lookup
from app.services.tenant_llm_config import get_decrypted_api_key
from app.utils.broadcast import broadcaster

import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


async def _broadcast_script_flow_index_update(
    *,
    agent_id: UUID,
    flow_id: UUID,
    index_status: str,
    published_version: int,
    index_error: str | None = None,
    index_progress: int | None = None,
) -> None:
    """Уведомить открытые WebSocket-клиенты об изменении статуса индексации потока."""
    payload: dict[str, Any] = {
        "type": "script_flow_index_updated",
        "data": {
            "agent_id": str(agent_id),
            "flow_id": str(flow_id),
            "index_status": index_status,
            "published_version": int(published_version or 0),
        },
    }
    if index_error is not None:
        payload["data"]["index_error"] = index_error
    if index_progress is not None:
        payload["data"]["index_progress"] = index_progress
    try:
        await broadcaster.publish(agent_id, payload)
    except Exception as exc:
        logger.warning(
            "script_flow_index_broadcast_failed",
            agent_id=str(agent_id),
            flow_id=str(flow_id),
            error=str(exc),
        )


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
    service_external_ids: list[str] = []
    skill_doc: dict[str, Any] | None = None
    compiled_text: str | None
    index_status: str
    index_error: str | None
    last_indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    index_progress: int | None = None
    index_retry_count: int | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None


class ScriptFlowCreate(BaseModel):
    name: str
    internal_note: str | None = None
    flow_metadata: dict[str, Any] = {}
    flow_definition: dict[str, Any] = {}
    service_external_ids: list[str] = []


class ScriptFlowUpdate(BaseModel):
    name: str | None = None
    internal_note: str | None = None
    flow_metadata: dict[str, Any] | None = None
    flow_definition: dict[str, Any] | None = None
    service_external_ids: list[str] | None = None


class CompileDraftBody(BaseModel):
    """Черновая компиляция с телом (sandbox / превью без сохранения)."""

    flow_definition: dict[str, Any] = {}
    flow_metadata: dict[str, Any] = {}


class GraphPreviewDraftBody(BaseModel):
    flow_definition: dict[str, Any] = {}
    flow_metadata: dict[str, Any] = {}


class GenerateFieldRequest(BaseModel):
    node_id: str
    node_type: str
    field_key: str
    current_node_data: dict[str, Any] = {}


class GenerateFieldResponse(BaseModel):
    field_key: str
    generated_text: str
    model: str
    tokens_in: int
    tokens_out: int


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
    include_deleted: bool = False,
) -> ScriptFlow:
    stmt = select(ScriptFlow).where(
        ScriptFlow.id == flow_id,
        ScriptFlow.agent_id == agent_id,
        ScriptFlow.tenant_id == tenant_id,
    )
    if not include_deleted:
        stmt = stmt.where(ScriptFlow.is_deleted.is_(False))
    flow = (await db.execute(stmt)).scalar_one_or_none()
    if flow is None:
        raise _api_error("not_found", "Script flow not found", status.HTTP_404_NOT_FOUND)
    return flow


async def _agent_has_indexed_flows(db: AsyncSession, *, agent_id: UUID, tenant_id: UUID) -> bool:
    stmt = (
        select(ScriptFlow.id)
        .where(
            ScriptFlow.agent_id == agent_id,
            ScriptFlow.tenant_id == tenant_id,
            ScriptFlow.is_deleted.is_(False),
            ScriptFlow.flow_status == "published",
            ScriptFlow.index_status == "indexed",
            ScriptFlow.indexed_version.is_not(None),
            ScriptFlow.indexed_version >= ScriptFlow.published_version,
        )
        .limit(1)
    )
    return (await db.scalar(stmt)) is not None


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
        .where(
            ScriptFlow.agent_id == agent_id,
            ScriptFlow.tenant_id == user.tenant_id,
            ScriptFlow.is_deleted.is_(False),
        )
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
        service_external_ids=list(payload.service_external_ids or []),
    )
    db.add(flow)
    await db.commit()
    await db.refresh(flow)
    return ScriptFlowRead.model_validate(flow)


@router.get("/script-flows/tactic-coverage/gap-clusters", response_model=dict)
async def get_script_flow_gap_clusters(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Получить последний снэпшот кластеров пробелов покрытия."""
    await get_agent_or_404(agent_id, db, user)
    from app.services.script_flow_gap_clustering import get_latest_clusters

    clusters = await get_latest_clusters(db, tenant_id=user.tenant_id, agent_id=agent_id)
    return {"clusters": clusters}


@router.post("/script-flows/tactic-coverage/gap-clusters/recompute", response_model=dict)
async def recompute_script_flow_gap_clusters(
    agent_id: UUID,
    period_days: int = 7,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Перекластеризовать запросы со слабым/нулевым матчем и обновить снэпшот.

    LLM-затратная операция: эмбеддит каждый уникальный запрос и делает по
    одному вызову на кластер для генерации читаемого названия.
    """
    await get_agent_or_404(agent_id, db, user)
    from app.services.script_flow_gap_clustering import (
        get_latest_clusters,
        recompute_gap_clusters,
    )

    period = max(1, min(int(period_days or 7), 90))
    saved = await recompute_gap_clusters(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        period_days=period,
    )
    clusters = await get_latest_clusters(
        db, tenant_id=user.tenant_id, agent_id=agent_id
    )
    return {"saved": saved, "clusters": clusters}


@router.get("/script-flows/tactic-coverage/missed-calls", response_model=dict)
async def get_script_flow_missed_calls(
    agent_id: UUID,
    period_days: int = 7,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Сводка по упущенным вызовам тула: запросы клиентов, классифицированные
    как objection/trigger/closing/concern, для которых LLM не позвала
    `search_expert_tactics`.
    """
    await get_agent_or_404(agent_id, db, user)
    from app.services.script_flow_missed_call_detector import get_missed_calls_summary

    period = max(1, min(int(period_days or 7), 30))
    return await get_missed_calls_summary(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        period_days=period,
    )


@router.post("/script-flows/tactic-coverage/missed-calls/detect", response_model=dict)
async def run_missed_call_detection(
    agent_id: UUID,
    period_hours: int = 24,
    max_runs: int = 60,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Запустить детектор упущенных вызовов: проходит по последним runs без
    `search_expert_tactics` и классифицирует сообщения клиентов LLM."""
    await get_agent_or_404(agent_id, db, user)
    from app.services.script_flow_missed_call_detector import (
        detect_missed_calls,
        get_missed_calls_summary,
    )

    hours = max(1, min(int(period_hours or 24), 168))
    runs = max(10, min(int(max_runs or 60), 500))
    saved = await detect_missed_calls(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        period_hours=hours,
        max_runs=runs,
    )
    summary = await get_missed_calls_summary(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        period_days=max(1, hours // 24 + 1),
    )
    return {"detected": saved, "summary": summary}


@router.get("/script-flows/tactic-coverage", response_model=dict)
async def get_script_flow_tactic_coverage(
    agent_id: UUID,
    period_days: int = 7,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Аналитика вызовов `search_expert_tactics`: покрытие, топ тактик, пробелы.

    Возвращает:
    - summary: распределение по релевантности (релевантных / слабых / мимо / без матча)
    - top_tactics: какие тактики чаще всего попадают в LLM
    - gap_queries: запросы с слабым/нерелевантным мэтчем — кандидаты на новые сценарии
    - no_match_queries: запросы, где поиск ничего не вернул
    """
    await get_agent_or_404(agent_id, db, user)
    from app.services.script_flow_coverage import (
        build_coverage_report,
        coverage_report_to_dict,
    )

    period = max(1, min(int(period_days or 7), 90))
    report = await build_coverage_report(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        period_days=period,
    )
    return coverage_report_to_dict(report)


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
    if payload.service_external_ids is not None:
        flow.service_external_ids = list(payload.service_external_ids)
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
    """Мягкое удаление — поток уходит в корзину, восстановим через /restore.

    Раньше было жёсткое db.delete (каскадом сносило версии/ноды и было
    невосстановимо). Теперь помечаем deleted_at; граф в Neo4j не трогаем.
    """
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    flow.is_deleted = True
    flow.deleted_at = datetime.now(timezone.utc)
    await db.commit()


@router.get("/script-flows-trash", response_model=list[ScriptFlowRead])
async def list_deleted_script_flows(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[ScriptFlowRead]:
    """Корзина потоков — удалённые (для восстановления)."""
    await get_agent_or_404(agent_id, db, user)
    stmt = (
        select(ScriptFlow)
        .where(
            ScriptFlow.agent_id == agent_id,
            ScriptFlow.tenant_id == user.tenant_id,
            ScriptFlow.is_deleted.is_(True),
        )
        .order_by(ScriptFlow.deleted_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [ScriptFlowRead.model_validate(r) for r in rows]


@router.post("/script-flows/{flow_id}/restore", response_model=ScriptFlowRead)
async def restore_script_flow(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ScriptFlowRead:
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(
        db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id, include_deleted=True
    )
    flow.is_deleted = False
    flow.deleted_at = None
    await db.commit()
    await db.refresh(flow)
    return ScriptFlowRead.model_validate(flow)


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

    # Дистилляция навыка (skill_doc) — best-effort и НЕ перезаписывает уже собранный
    # навык (в чате/вручную). Автозаполняем только пустой skill_doc — например при
    # первой публикации навыка, собранного из графа-сценария.
    existing_doc = flow.skill_doc if isinstance(flow.skill_doc, dict) else None
    already_authored = bool(existing_doc and (existing_doc.get("objections") or existing_doc.get("gaps")))
    if not already_authored and (compiled_text or "").strip():
        if openai_api_key := await get_decrypted_api_key(db, flow.tenant_id):
            try:
                flow.skill_doc = await distill_skill(
                    compiled_text,
                    flow.name,
                    openai_api_key=openai_api_key,
                )
            except Exception:  # noqa: BLE001
                logger.exception("skill_distill_failed_on_publish", flow_id=str(flow.id))

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
    await _broadcast_script_flow_index_update(
        agent_id=agent_id,
        flow_id=flow.id,
        index_status=flow.index_status,
        published_version=int(flow.published_version or 0),
    )
    return {
        "id": str(flow.id),
        "flow_status": flow.flow_status,
        "published_version": flow.published_version,
        "index_status": flow.index_status,
    }


@router.post("/script-flows/{flow_id}/distill-skill", response_model=dict)
async def distill_script_flow_skill(
    agent_id: UUID,
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Пересобрать skill_doc из текущего compiled_text потока (ручной переген).

    Не публикует и не переиндексирует — только обновляет дистиллированную
    структуру навыка. Требует, чтобы поток был скомпилирован (compiled_text).
    """
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    if not (flow.compiled_text or "").strip():
        raise _api_error(
            "not_compiled",
            "Навык ещё не скомпилирован — опубликуйте поток перед дистилляцией.",
            status.HTTP_409_CONFLICT,
        )
    openai_api_key = await get_decrypted_api_key(db, flow.tenant_id)
    if not openai_api_key:
        raise _api_error(
            "no_llm_key",
            "Не настроен ключ OpenAI для тенанта.",
            status.HTTP_400_BAD_REQUEST,
        )
    try:
        skill_doc = await distill_skill(
            flow.compiled_text,
            flow.name,
            openai_api_key=openai_api_key,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("skill_distill_failed", flow_id=str(flow.id))
        raise _api_error("distill_error", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY) from exc

    flow.skill_doc = skill_doc
    await db.commit()
    await db.refresh(flow)
    return {
        "id": str(flow.id),
        "skill_doc": skill_doc,
        "objections": len(skill_doc.get("objections") or []),
        "gaps": len(skill_doc.get("gaps") or []),
    }


class SkillChatMessage(BaseModel):
    role: str
    content: str


class SkillChatAttachment(BaseModel):
    name: str
    text: str


# Модели, доступные для выбора в ассистенте навыка (белый список).
SKILL_CHAT_MODELS: list[dict[str, str]] = [
    {"id": "openai:gpt-4.1", "label": "GPT-4.1", "hint": "быстро, дёшево"},
    {"id": "openai:gpt-5.1", "label": "GPT-5.1", "hint": "размышляет, точнее"},
    {"id": "openai:gpt-4o-mini", "label": "GPT-4o mini", "hint": "самый дешёвый"},
]
_SKILL_CHAT_MODEL_IDS = {m["id"] for m in SKILL_CHAT_MODELS}


class SkillChatBody(BaseModel):
    messages: list[SkillChatMessage] = []
    attachments: list[SkillChatAttachment] = []
    skill_doc: dict[str, Any] | None = None
    model: str | None = None


@router.get("/script-flows/skill-chat/models", response_model=dict)
async def list_skill_chat_models(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Список моделей, доступных для ассистента сборки навыка."""
    return {"models": SKILL_CHAT_MODELS, "default": get_settings().skill_chat_model}


@router.post("/script-flows/{flow_id}/skill-chat", response_model=dict)
async def skill_chat(
    agent_id: UUID,
    flow_id: UUID,
    body: SkillChatBody,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Разговорная сборка навыка: эксперт в чате + материалах передаёт опыт → skill_doc.

    Ассистент структурирует ТОЛЬКО то, что дал эксперт (реплики + вложения), не
    выдумывает. Возвращает ответ ассистента + обновлённый skill_doc (не сохраняет —
    сохранение отдельным PATCH /skill-doc по кнопке «Применить»).
    """
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    openai_api_key = await get_decrypted_api_key(db, flow.tenant_id)
    if not openai_api_key:
        raise _api_error("no_llm_key", "Не настроен ключ OpenAI для тенанта.", status.HTTP_400_BAD_REQUEST)
    chosen_model = body.model if body.model in _SKILL_CHAT_MODEL_IDS else None
    try:
        result = await converse_skill(
            messages=[m.model_dump() for m in body.messages],
            attachments=[a.model_dump() for a in body.attachments],
            current_skill_doc=body.skill_doc if body.skill_doc is not None else flow.skill_doc,
            service_name=flow.name,
            openai_api_key=openai_api_key,
            model=chosen_model,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("skill_chat_failed", flow_id=str(flow.id))
        raise _api_error("skill_chat_error", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY) from exc
    additions = result["additions"]
    return {
        "reply": result["reply"],
        "additions": additions,
        "added_objections": len(additions.get("objections") or []),
        "added_gaps": len(additions.get("gaps") or []),
    }


@router.post("/script-flows/{flow_id}/skill-chat/stream")
async def skill_chat_stream(
    agent_id: UUID,
    flow_id: UUID,
    body: SkillChatBody,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> EventSourceResponse:
    """Потоковая версия skill-chat: reply приходит по мере генерации (SSE).

    События: `delta` {text} — прирост ответа; `done` {reply, additions} — финал;
    `error` {error}.
    """
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    openai_api_key = await get_decrypted_api_key(db, flow.tenant_id)
    if not openai_api_key:
        raise _api_error("no_llm_key", "Не настроен ключ OpenAI для тенанта.", status.HTTP_400_BAD_REQUEST)
    chosen_model = body.model if body.model in _SKILL_CHAT_MODEL_IDS else None
    current_doc = body.skill_doc if body.skill_doc is not None else flow.skill_doc
    msgs = [m.model_dump() for m in body.messages]
    atts = [a.model_dump() for a in body.attachments]
    flow_name = flow.name

    async def event_generator():
        try:
            async for kind, payload in converse_skill_stream(
                messages=msgs,
                attachments=atts,
                current_skill_doc=current_doc,
                service_name=flow_name,
                openai_api_key=openai_api_key,
                model=chosen_model,
            ):
                if kind == "delta":
                    yield {"event": "delta", "data": json.dumps({"text": payload})}
                elif kind == "done":
                    yield {"event": "done", "data": json.dumps(payload, ensure_ascii=False)}
        except Exception as exc:  # noqa: BLE001
            logger.exception("skill_chat_stream_failed", flow_id=str(flow_id))
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}

    # Заголовки против буферизации SSE прокси (nginx/Caddy) — чтобы дельты
    # доходили до браузера сразу, а не пачкой в конце.
    return EventSourceResponse(
        event_generator(),
        ping=15,
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


class SkillDocPatch(BaseModel):
    skill_doc: dict[str, Any]


@router.patch("/script-flows/{flow_id}/skill-doc", response_model=dict)
async def update_script_flow_skill_doc(
    agent_id: UUID,
    flow_id: UUID,
    payload: SkillDocPatch,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Сохранить ручные правки структуры навыка (skill_doc).

    Правки эксперта из редактора навыка. Нормализуем той же логикой, что и
    дистилляцию (инвариант: обработка без фраз → пробел). ВНИМАНИЕ: повторная
    дистилляция/публикация перезапишет эти правки — это осознанный выбор
    (источник истины — сценарий, skill_doc производный, но редактируемый).
    """
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    normalized = _sanitize_skill_doc(payload.skill_doc or {})
    flow.skill_doc = normalized
    await db.commit()
    await db.refresh(flow)
    return {
        "id": str(flow.id),
        "skill_doc": normalized,
        "objections": len(normalized.get("objections") or []),
        "gaps": len(normalized.get("gaps") or []),
    }


@router.get("/script-flows/{flow_id}/review-dialogs", response_model=dict)
async def get_script_flow_review_dialogs(
    agent_id: UUID,
    flow_id: UUID,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Реальные ходы агента по услугам этого навыка — основа ревью-инбокса.

    Берём сессии, где resolve_clinic_facts определил одну из услуг навыка, и
    возвращаем последние ходы (вход пациента → ответ агента). Если у навыка нет
    привязанных услуг — отдаём последние диалоги агента (чтобы страница не пустела).
    """
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    svc_ids = [str(x) for x in (flow.service_external_ids or []) if str(x).strip()]
    lim = max(1, min(int(limit or 30), 100))

    params: dict[str, Any] = {"aid": agent_id, "lim": lim}
    if svc_ids:
        # сессии, где определялась одна из услуг навыка
        params["svcs"] = svc_ids
        rows = (
            await db.execute(
                text(
                    """
                    WITH skill_sessions AS (
                        SELECT DISTINCT r.session_id
                        FROM tool_call_logs tcl
                        JOIN runs r ON r.id = tcl.run_id
                        WHERE r.agent_id = :aid
                          AND tcl.tool_name = 'resolve_clinic_facts'
                          AND (
                            (tcl.response_payload #>> '{resolved,service_external_id}') = ANY(:svcs)
                            OR EXISTS (
                              SELECT 1
                              FROM jsonb_array_elements(
                                COALESCE(tcl.response_payload->'services', '[]'::jsonb)
                              ) AS svc
                              WHERE (svc->>'external_id') = ANY(:svcs)
                            )
                          )
                    )
                    SELECT r.id, r.session_id, r.input_message, r.output_message,
                           r.tools_called, r.created_at
                    FROM runs r
                    JOIN skill_sessions s ON s.session_id = r.session_id
                    WHERE r.agent_id = :aid AND r.status = 'succeeded'
                    ORDER BY r.created_at DESC
                    LIMIT :lim
                    """
                ),
                params,
            )
        ).fetchall()
    else:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT r.id, r.session_id, r.input_message, r.output_message,
                           r.tools_called, r.created_at
                    FROM runs r
                    WHERE r.agent_id = :aid AND r.status = 'succeeded'
                    ORDER BY r.created_at DESC
                    LIMIT :lim
                    """
                ),
                params,
            )
        ).fetchall()

    dialogs = [
        {
            "run_id": str(row.id),
            "session_id": row.session_id,
            "input": row.input_message,
            "output": row.output_message,
            "tool_names": [
                c.get("name")
                for c in (row.tools_called or [])
                if isinstance(c, dict) and c.get("name")
            ],
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
    return {"dialogs": dialogs, "has_service_link": bool(svc_ids)}


class ReviewCorrectionBody(BaseModel):
    situation: str
    trigger_when: str = ""
    approach: str = ""
    phrase: str | None = None
    level: str = "пример"
    # верно / ушёл в генерик / пережал — пометка ревьюера (для аналитики)
    mark: str | None = None


@router.post("/script-flows/{flow_id}/review-correction", response_model=dict)
async def add_script_flow_review_correction(
    agent_id: UUID,
    flow_id: UUID,
    body: ReviewCorrectionBody,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Правка из ревью → в skill_doc.

    Если дана фраза «как надо» — добавляем обработку (objection) с этой фразой и
    её уровнем дословности. Если фразы нет — фиксируем как пробел (gap).
    """
    await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)
    doc = copy.deepcopy(flow.skill_doc) if isinstance(flow.skill_doc, dict) else {}
    doc.setdefault("context", "")
    for key in ("objections", "sequence", "facts_from_tool", "endings", "gaps"):
        doc.setdefault(key, [])

    situation = (body.situation or "").strip()
    if not situation:
        raise _api_error("empty_situation", "Ситуация обязательна.", status.HTTP_422_UNPROCESSABLE_ENTITY)

    phrase = (body.phrase or "").strip()
    if phrase:
        level = body.level if body.level in ("пример", "дословно", "обязательно") else "пример"
        doc["objections"].append(
            {
                "situation": situation,
                "trigger_when": (body.trigger_when or "").strip(),
                "approach": (body.approach or "").strip(),
                "phrases": [{"text": phrase, "level": level}],
                "forbidden": [],
            }
        )
    else:
        doc["gaps"].append(
            {"situation": situation, "trigger_when": (body.trigger_when or "").strip()}
        )

    normalized = _sanitize_skill_doc(doc)
    flow.skill_doc = normalized
    await db.commit()
    await db.refresh(flow)
    return {
        "id": str(flow.id),
        "skill_doc": normalized,
        "objections": len(normalized.get("objections") or []),
        "gaps": len(normalized.get("gaps") or []),
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
    await _broadcast_script_flow_index_update(
        agent_id=agent_id,
        flow_id=flow.id,
        index_status=flow.index_status,
        published_version=int(flow.published_version or 0),
    )
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
    await _broadcast_script_flow_index_update(
        agent_id=agent_id,
        flow_id=flow.id,
        index_status=flow.index_status,
        published_version=int(flow.published_version or 0),
    )
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

    rows = (
        await db.execute(
            select(ScriptFlow.id, ScriptFlow.published_version).where(ScriptFlow.id.in_(flow_ids)),
        )
    ).all()
    for fid, pub_ver in rows:
        await _broadcast_script_flow_index_update(
            agent_id=agent_id,
            flow_id=fid,
            index_status="pending",
            published_version=int(pub_ver or 0),
        )

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


@router.post(
    "/script-flows/{flow_id}/nodes/generate-field",
    response_model=GenerateFieldResponse,
)
async def generate_node_field(
    agent_id: UUID,
    flow_id: UUID,
    payload: GenerateFieldRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> GenerateFieldResponse:
    from decimal import Decimal

    from app.db.models.model_pricing import ModelPricing
    from app.services.script_flow_field_generator import (
        generate_field_value,
        _normalize_openai_model,
    )
    from app.services.script_flow_field_meta import field_key_node_type, get_field_ai_meta
    from app.services.tenant_balance import apply_balance_charge

    agent = await get_agent_or_404(agent_id, db, user)
    flow = await _get_flow_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=flow_id)

    field_key = (payload.field_key or "").strip()
    field_meta = get_field_ai_meta(field_key)
    if field_meta is None:
        raise _api_error(
            "unknown_field_key",
            f"Field {field_key!r} is not eligible for AI auto-fill",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    expected_type = field_key_node_type(field_key)
    if expected_type and expected_type != payload.node_type:
        raise _api_error(
            "node_type_mismatch",
            f"field_key prefix {expected_type!r} does not match node_type {payload.node_type!r}",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    field_name = field_key.split(".", 1)[1] if "." in field_key else field_key

    fd = flow.flow_definition or {}
    nodes_list = fd.get("nodes") if isinstance(fd, dict) else None
    nodes_list = nodes_list if isinstance(nodes_list, list) else []
    target_node = next(
        (n for n in nodes_list if isinstance(n, dict) and str(n.get("id")) == payload.node_id),
        None,
    )
    if target_node is None:
        raise _api_error(
            "node_not_found",
            f"Node {payload.node_id!r} not found in flow",
            status.HTTP_404_NOT_FOUND,
        )

    openai_api_key = await get_decrypted_api_key(db, user.tenant_id)
    if not (openai_api_key or "").strip():
        raise _api_error(
            "no_openai_key",
            "Подключите OpenAI API ключ в настройках LLM-провайдеров",
            status.HTTP_409_CONFLICT,
        )

    try:
        result = await generate_field_value(
            agent_system_prompt=agent.system_prompt or "",
            agent_model=agent.model,
            flow_name=flow.name or "",
            node_id=payload.node_id,
            node_type=payload.node_type,
            field_key=field_key,
            field_name=field_name,
            current_node_data=payload.current_node_data or {},
            flow_definition=fd,
            openai_api_key=openai_api_key,
        )
    except ValueError as exc:
        raise _api_error(
            "generation_failed",
            str(exc),
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "script_flow_field_generate_failed",
            field_key=field_key,
            node_id=payload.node_id,
            error=str(exc),
        )
        raise _api_error(
            "openai_unavailable",
            "OpenAI временно недоступен, повторите попытку позже",
            status.HTTP_502_BAD_GATEWAY,
        ) from exc

    pricing_model = _normalize_openai_model(result.model)
    pricing_stmt = (
        select(ModelPricing)
        .where(
            ModelPricing.provider == "openai",
            ModelPricing.model_name == pricing_model,
            ModelPricing.is_active.is_(True),
        )
        .limit(1)
    )
    pricing = (await db.execute(pricing_stmt)).scalar_one_or_none()
    if pricing is not None and (result.tokens_in or result.tokens_out):
        million = Decimal("1000000")
        amount = (
            Decimal(result.tokens_in) * Decimal(pricing.input_usd) / million
            + Decimal(result.tokens_out) * Decimal(pricing.output_usd) / million
        )
        if amount > 0:
            ts_ms = int(time.time() * 1000)
            try:
                await apply_balance_charge(
                    db,
                    tenant_id=user.tenant_id,
                    amount_usd=amount,
                    source_type="script_flow_field_ai",
                    source_id=f"{flow_id}:{payload.node_id}:{field_key}:{ts_ms}",
                    metadata={
                        "model": pricing_model,
                        "tokens_in": result.tokens_in,
                        "tokens_out": result.tokens_out,
                        "field_key": field_key,
                    },
                )
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "script_flow_field_billing_failed",
                    field_key=field_key,
                    error=str(exc),
                )

    return GenerateFieldResponse(
        field_key=field_key,
        generated_text=result.generated_text,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
    )


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

    from app.services.runtime.script_flow_retriever import ScriptFlowRetriever

    if not await _agent_has_indexed_flows(db, agent_id=agent_id, tenant_id=user.tenant_id):
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
