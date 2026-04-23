"""CRUD для общей библиотеки KG-сущностей уровня агента.

Сущности (Motive/Argument/Proof/Objection/Constraint/Outcome) переиспользуются
между потоками — узлы потоков ссылаются на них по id из
`flow_definition.nodes[].data.kg_links.<type>_ids[]`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog
from sqlalchemy import update as sa_update

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.db.models.agent_kg_entity import ENTITY_TYPES, AgentKgEntity
from app.db.models.script_flow import ScriptFlow
from app.services.script_flow_kg_cleanup import strip_kg_entity_from_all_agent_flows
from app.db.session import get_db
from app.schemas.auth import AuthContext

logger = structlog.get_logger(__name__)


async def _mark_indexed_flows_pending(
    db: AsyncSession, *, agent_id: UUID, tenant_id: UUID
) -> int:
    """Сбрасывает index_status='indexed' → 'pending' для всех опубликованных
    потоков агента, чтобы index-worker переиндексировал их с актуальными
    KG-сущностями.

    Возвращает количество затронутых потоков.
    """
    stmt = (
        sa_update(ScriptFlow)
        .where(
            ScriptFlow.agent_id == agent_id,
            ScriptFlow.tenant_id == tenant_id,
            ScriptFlow.flow_status == "published",
            ScriptFlow.index_status == "indexed",
        )
        .values(index_status="pending")
        .returning(ScriptFlow.id)
    )
    result = await db.execute(stmt)
    count = len(result.fetchall())
    if count:
        logger.info(
            "kg_entity_changed_flows_reset_to_pending",
            agent_id=str(agent_id),
            flows_reset=count,
        )
    return count

router = APIRouter()


def _api_error(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"error": code, "message": message, "detail": message, "field_errors": None},
    )


# ── Schemas ───────────────────────────────────────────────────────────────────


class KgEntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    tenant_id: UUID
    entity_type: str
    name: str
    description: str | None
    meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None
    usage_count: int = 0


class KgEntityCreate(BaseModel):
    entity_type: str = Field(..., description="motive | argument | proof | objection | constraint | outcome")
    name: str
    description: str | None = None
    meta: dict[str, Any] = {}


class KgEntityUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    meta: dict[str, Any] | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _validate_type(entity_type: str) -> None:
    if entity_type not in ENTITY_TYPES:
        raise _api_error(
            "invalid_entity_type",
            f"entity_type must be one of: {', '.join(ENTITY_TYPES)}",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


async def _compute_usage_counts(
    db: AsyncSession, *, agent_id: UUID, tenant_id: UUID
) -> dict[str, int]:
    """Считаем, в скольких узлах каждая сущность упомянута в kg_links.

    Делаем одним запросом — парсим JSONB во всех flow_definition.
    """
    stmt = select(ScriptFlow.flow_definition).where(
        ScriptFlow.agent_id == agent_id,
        ScriptFlow.tenant_id == tenant_id,
    )
    rows = (await db.execute(stmt)).scalars().all()
    counts: dict[str, int] = {}
    link_keys = (
        "motive_ids",
        "argument_ids",
        "proof_ids",
        "objection_ids",
        "constraint_ids",
    )
    for fd in rows:
        if not isinstance(fd, dict):
            continue
        nodes = fd.get("nodes") or []
        if not isinstance(nodes, list):
            continue
        for n in nodes:
            if not isinstance(n, dict):
                continue
            data = n.get("data") or {}
            if not isinstance(data, dict):
                continue
            links = data.get("kg_links") or {}
            if not isinstance(links, dict):
                continue
            for k in link_keys:
                vals = links.get(k) or []
                if isinstance(vals, list):
                    for v in vals:
                        key = str(v)
                        counts[key] = counts.get(key, 0) + 1
            outcome_id = links.get("outcome_id")
            if outcome_id:
                key = str(outcome_id)
                counts[key] = counts.get(key, 0) + 1
    return counts


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/kg-entities", response_model=list[KgEntityRead])
async def list_entities(
    agent_id: UUID,
    type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[KgEntityRead]:
    await get_agent_or_404(agent_id, db, user)
    conds = [AgentKgEntity.agent_id == agent_id, AgentKgEntity.tenant_id == user.tenant_id]
    if type:
        _validate_type(type)
        conds.append(AgentKgEntity.entity_type == type)
    stmt = select(AgentKgEntity).where(and_(*conds)).order_by(
        AgentKgEntity.entity_type.asc(), AgentKgEntity.name.asc()
    )
    rows = (await db.execute(stmt)).scalars().all()
    usage = await _compute_usage_counts(db, agent_id=agent_id, tenant_id=user.tenant_id)
    out: list[KgEntityRead] = []
    for r in rows:
        item = KgEntityRead.model_validate(r)
        item.usage_count = usage.get(str(r.id), 0)
        out.append(item)
    return out


@router.post(
    "/kg-entities",
    response_model=KgEntityRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_entity(
    agent_id: UUID,
    payload: KgEntityCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> KgEntityRead:
    await get_agent_or_404(agent_id, db, user)
    _validate_type(payload.entity_type)
    name = payload.name.strip()
    if not name:
        raise _api_error("invalid_name", "name is required", status.HTTP_422_UNPROCESSABLE_ENTITY)

    name_lc = name.lower()
    existing_stmt = select(AgentKgEntity).where(
        AgentKgEntity.agent_id == agent_id,
        AgentKgEntity.entity_type == payload.entity_type,
        AgentKgEntity.name_lc == name_lc,
    )
    if (await db.execute(existing_stmt)).scalar_one_or_none():
        raise _api_error(
            "duplicate_name",
            f"Сущность «{name}» уже существует в типе {payload.entity_type}",
            status.HTTP_409_CONFLICT,
        )

    entity = AgentKgEntity(
        id=uuid4(),
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        entity_type=payload.entity_type,
        name=name,
        name_lc=name_lc,
        description=payload.description,
        meta=payload.meta or {},
    )
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    # Новый мотив/возражение/аргумент может изменить стиль ответов —
    # сбрасываем индекс потоков, чтобы индекс переиндексировался с актуальными данными.
    await _mark_indexed_flows_pending(db, agent_id=agent_id, tenant_id=user.tenant_id)
    await db.commit()
    return KgEntityRead.model_validate(entity)


@router.patch("/kg-entities/{entity_id}", response_model=KgEntityRead)
async def update_entity(
    agent_id: UUID,
    entity_id: UUID,
    payload: KgEntityUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> KgEntityRead:
    await get_agent_or_404(agent_id, db, user)
    stmt = select(AgentKgEntity).where(
        AgentKgEntity.id == entity_id,
        AgentKgEntity.agent_id == agent_id,
        AgentKgEntity.tenant_id == user.tenant_id,
    )
    entity = (await db.execute(stmt)).scalar_one_or_none()
    if entity is None:
        raise _api_error("not_found", "Entity not found", status.HTTP_404_NOT_FOUND)

    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise _api_error("invalid_name", "name cannot be empty", status.HTTP_422_UNPROCESSABLE_ENTITY)
        new_name_lc = new_name.lower()
        if new_name_lc != entity.name_lc:
            dup_stmt = select(AgentKgEntity).where(
                AgentKgEntity.agent_id == agent_id,
                AgentKgEntity.entity_type == entity.entity_type,
                AgentKgEntity.name_lc == new_name_lc,
                AgentKgEntity.id != entity_id,
            )
            if (await db.execute(dup_stmt)).scalar_one_or_none():
                raise _api_error(
                    "duplicate_name",
                    f"Сущность «{new_name}» уже существует",
                    status.HTTP_409_CONFLICT,
                )
        entity.name = new_name
        entity.name_lc = new_name_lc
    if payload.description is not None:
        entity.description = payload.description
    if payload.meta is not None:
        entity.meta = payload.meta

    await db.commit()
    await db.refresh(entity)
    # communication_style / preferred_phrases могли измениться —
    # переиндексируем потоки агента.
    await _mark_indexed_flows_pending(db, agent_id=agent_id, tenant_id=user.tenant_id)
    await db.commit()
    return KgEntityRead.model_validate(entity)


@router.delete("/kg-entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    agent_id: UUID,
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    await get_agent_or_404(agent_id, db, user)
    stmt = select(AgentKgEntity).where(
        AgentKgEntity.id == entity_id,
        AgentKgEntity.agent_id == agent_id,
        AgentKgEntity.tenant_id == user.tenant_id,
    )
    entity = (await db.execute(stmt)).scalar_one_or_none()
    if entity is None:
        raise _api_error("not_found", "Entity not found", status.HTTP_404_NOT_FOUND)

    await strip_kg_entity_from_all_agent_flows(
        db,
        agent_id=agent_id,
        tenant_id=user.tenant_id,
        entity_id=entity_id,
    )

    await db.delete(entity)
    await db.commit()
    # Сущность удалена из узлов — переиндексируем потоки.
    await _mark_indexed_flows_pending(db, agent_id=agent_id, tenant_id=user.tenant_id)
    await db.commit()
