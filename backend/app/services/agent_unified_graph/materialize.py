"""Структурный материализатор unified-графа.

Идея: граф визуализации = чистая структура из таблиц БД.
- Узлы: специалисты, услуги, категории, Q&A, элементы справочников, узлы script-flow.
- Рёбра: только явные FK-связи (specialist↔service, service↔category, ...).

LLM не вызывается. Никаких узлов вроде «КЛИЕНТ»/«ПОДРУГА» — их в БД нет.
Семантическое обогащение (ребра по эмбеддингам) — отдельный слой, не здесь.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_unified_graph_node import AgentUnifiedGraphNode
from app.db.models.agent_unified_graph_relation import AgentUnifiedGraphRelation
from app.db.models.direct_question import DirectQuestion
from app.db.models.directory import Directory, DirectoryItem
from app.db.models.script_flow_graph_node import ScriptFlowGraphNode
from app.db.models.script_flow_graph_relation import ScriptFlowGraphRelation
from app.db.models.sqns_service import (
    SqnsResource,
    SqnsService,
    SqnsServiceCategory,
    SqnsServiceResource,
)

log = structlog.get_logger(__name__)

PROVENANCE = "structured"


@dataclass
class MaterializeResult:
    nodes: int
    relations: int
    by_type: dict[str, int]


# --- ID конструкторы (детерминированные, стабильные между ребилдами) ---

def _id_specialist(external_id: int) -> str:
    return f"specialist:{external_id}"


def _id_service(external_id: int) -> str:
    return f"service:{external_id}"


def _id_category(category_id: UUID) -> str:
    return f"category:{category_id}"


def _id_question(question_id: UUID) -> str:
    return f"question:{question_id}"


def _id_directory(directory_id: UUID) -> str:
    return f"directory:{directory_id}"


def _id_directory_item(item_id: UUID) -> str:
    return f"directory_item:{item_id}"


def _id_script_node(graph_node_id: str) -> str:
    # Узлы скрипт-флоу уже имеют свой stable graph_node_id, добавляем префикс
    # чтобы не конфликтовать с пространством unified-графа.
    return f"script:{graph_node_id}"


# --- Сборка узлов ---

async def _build_specialists(db: AsyncSession, agent_id: UUID) -> list[dict]:
    rows = (
        await db.execute(
            select(SqnsResource).where(
                SqnsResource.agent_id == agent_id,
                SqnsResource.is_active == True,  # noqa: E712
                SqnsResource.active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    nodes = []
    for r in rows:
        nodes.append({
            "graph_node_id": _id_specialist(r.external_id),
            "origin_slice": "sqns",
            "entity_type": "specialist",
            "title": r.name,
            "description": r.information,
            "domain_entity_id": r.id,
            "properties": {
                "specialization": r.specialization,
                "external_id": r.external_id,
            },
        })
    return nodes


async def _build_services(db: AsyncSession, agent_id: UUID) -> list[dict]:
    rows = (
        await db.execute(
            select(SqnsService).where(
                SqnsService.agent_id == agent_id,
                SqnsService.is_enabled == True,  # noqa: E712
            )
        )
    ).scalars().all()
    nodes = []
    for s in rows:
        nodes.append({
            "graph_node_id": _id_service(s.external_id),
            "origin_slice": "sqns",
            "entity_type": "service",
            "title": s.name,
            "description": s.description,
            "domain_entity_id": s.id,
            "properties": {
                "category": s.category,
                "duration_seconds": s.duration_seconds,
                "external_id": s.external_id,
            },
        })
    return nodes


async def _build_categories(db: AsyncSession, agent_id: UUID) -> list[dict]:
    rows = (
        await db.execute(
            select(SqnsServiceCategory).where(
                SqnsServiceCategory.agent_id == agent_id,
                SqnsServiceCategory.is_enabled == True,  # noqa: E712
                SqnsServiceCategory.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    nodes = []
    for c in rows:
        nodes.append({
            "graph_node_id": _id_category(c.id),
            "origin_slice": "sqns",
            "entity_type": "category",
            "title": c.name,
            "description": None,
            "domain_entity_id": c.id,
            "properties": {"priority": c.priority},
        })
    return nodes


async def _build_questions(db: AsyncSession, agent_id: UUID) -> list[dict]:
    rows = (
        await db.execute(
            select(DirectQuestion).where(
                DirectQuestion.agent_id == agent_id,
                DirectQuestion.is_enabled == True,  # noqa: E712
            )
        )
    ).scalars().all()
    nodes = []
    for q in rows:
        nodes.append({
            "graph_node_id": _id_question(q.id),
            "origin_slice": "knowledge",
            "entity_type": "question",
            "title": q.title,
            "description": q.content,
            "domain_entity_id": q.id,
            "properties": {"tags": list(q.tags or [])},
        })
    return nodes


async def _build_directory_items(db: AsyncSession, agent_id: UUID) -> tuple[list[dict], list[dict]]:
    """Справочники + их элементы. Возвращает (узлы_справочников, узлы_элементов)."""
    directories = (
        await db.execute(
            select(Directory).where(
                Directory.agent_id == agent_id,
                Directory.is_enabled == True,  # noqa: E712
                Directory.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()
    if not directories:
        return [], []

    dir_nodes = []
    for d in directories:
        # ВАЖНО: tool_description содержит мета-инструкцию для LLM
        # ("Инструмент `get_question_answer`. Вызывай, когда..."), а не доменное
        # описание справочника. Не пропускаем её в граф — она засоряет
        # keyword-matcher семантического слоя и панель деталей.
        dir_nodes.append({
            "graph_node_id": _id_directory(d.id),
            "origin_slice": "directory",
            "entity_type": "directory",
            "title": d.name,
            "description": None,
            "domain_entity_id": d.id,
            "properties": {"template": d.template, "tool_name": d.tool_name},
        })

    dir_ids = [d.id for d in directories]
    items = (
        await db.execute(
            select(DirectoryItem).where(DirectoryItem.directory_id.in_(dir_ids))
        )
    ).scalars().all()

    item_nodes = []
    for it in items:
        title_field = _pick_title_from_data(it.data) or "—"
        item_nodes.append({
            "graph_node_id": _id_directory_item(it.id),
            "origin_slice": "directory",
            "entity_type": "directory_item",
            "title": title_field[:480],
            "description": _pick_description_from_data(it.data),
            "domain_entity_id": it.id,
            "properties": {"directory_id": str(it.directory_id)},
        })
    return dir_nodes, item_nodes


def _pick_title_from_data(data: dict | None) -> str | None:
    if not data:
        return None
    for key in ("title", "name", "label", "question"):
        v = data.get(key)
        if v and isinstance(v, str):
            return v.strip()
    return None


def _pick_description_from_data(data: dict | None) -> str | None:
    if not data:
        return None
    for key in ("description", "content", "answer", "details"):
        v = data.get(key)
        if v and isinstance(v, str):
            return v.strip()
    return None


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
# Entity types that are structural metadata — not useful as standalone graph nodes
_SKIP_SCRIPT_ENTITY_TYPES = frozenset({"stage", "end"})


async def _build_script_flow_nodes(db: AsyncSession, agent_id: UUID) -> list[dict]:
    rows = (
        await db.execute(
            select(ScriptFlowGraphNode).where(ScriptFlowGraphNode.agent_id == agent_id)
        )
    ).scalars().all()
    nodes = []
    for n in rows:
        etype = (n.entity_type or "entity").lower()
        # Skip structural metadata nodes that add no value in the visual graph
        if etype in _SKIP_SCRIPT_ENTITY_TYPES:
            continue
        # Skip placeholder nodes whose title is just a UUID (no readable label)
        if _UUID_RE.match((n.title or "").strip()):
            continue
        nodes.append({
            "graph_node_id": _id_script_node(n.graph_node_id),
            "origin_slice": "script_bridge",
            "entity_type": etype,
            "title": n.title,
            "description": n.description,
            "domain_entity_id": None,
            "properties": {
                "node_kind": n.node_kind,
                "community_key": n.community_key,
                "flow_id": str(n.flow_id),
            },
        })
    return nodes


# --- Сборка рёбер (только явные FK) ---

async def _link_specialist_service(
    db: AsyncSession,
    agent_id: UUID,
    visible_node_ids: set[str],
) -> list[dict]:
    rows = (
        await db.execute(
            select(SqnsServiceResource, SqnsService.external_id, SqnsResource.external_id)
            .join(SqnsService, SqnsServiceResource.service_id == SqnsService.id)
            .join(SqnsResource, SqnsServiceResource.resource_id == SqnsResource.id)
            .where(SqnsService.agent_id == agent_id, SqnsResource.agent_id == agent_id)
        )
    ).all()
    edges = []
    for _link, srv_ext, res_ext in rows:
        sid = _id_specialist(res_ext)
        tid = _id_service(srv_ext)
        if sid not in visible_node_ids or tid not in visible_node_ids:
            continue
        edges.append({
            "source_graph_node_id": sid,
            "target_graph_node_id": tid,
            "relation_type": "оказывает",
            "weight": 1.0,
            "origin_slice": "sqns",
        })
    return edges


async def _link_service_category(
    db: AsyncSession,
    agent_id: UUID,
    visible_node_ids: set[str],
) -> list[dict]:
    """Связь по имени категории: sqns_services.category == sqns_service_categories.name."""
    cats = (
        await db.execute(
            select(SqnsServiceCategory).where(
                SqnsServiceCategory.agent_id == agent_id,
                SqnsServiceCategory.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    cat_by_name = {c.name: c for c in cats}

    services = (
        await db.execute(
            select(SqnsService).where(
                SqnsService.agent_id == agent_id,
                SqnsService.is_enabled == True,  # noqa: E712
            )
        )
    ).scalars().all()

    edges = []
    for s in services:
        if not s.category:
            continue
        cat = cat_by_name.get(s.category)
        if cat is None:
            continue
        sid = _id_service(s.external_id)
        tid = _id_category(cat.id)
        if sid not in visible_node_ids or tid not in visible_node_ids:
            continue
        edges.append({
            "source_graph_node_id": sid,
            "target_graph_node_id": tid,
            "relation_type": "входит в",
            "weight": 1.0,
            "origin_slice": "sqns",
        })
    return edges


async def _link_directory_items(
    db: AsyncSession,
    agent_id: UUID,
    visible_node_ids: set[str],
) -> list[dict]:
    """Каждый item принадлежит своему directory."""
    directories = (
        await db.execute(
            select(Directory.id).where(
                Directory.agent_id == agent_id,
                Directory.is_enabled == True,  # noqa: E712
                Directory.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()
    if not directories:
        return []
    items = (
        await db.execute(
            select(DirectoryItem).where(DirectoryItem.directory_id.in_(directories))
        )
    ).scalars().all()
    edges = []
    for it in items:
        sid = _id_directory_item(it.id)
        tid = _id_directory(it.directory_id)
        if sid not in visible_node_ids or tid not in visible_node_ids:
            continue
        edges.append({
            "source_graph_node_id": sid,
            "target_graph_node_id": tid,
            "relation_type": "входит в",
            "weight": 1.0,
            "origin_slice": "directory",
        })
    return edges


async def _link_script_flow_relations(
    db: AsyncSession,
    agent_id: UUID,
    visible_node_ids: set[str],
) -> list[dict]:
    rows = (
        await db.execute(
            select(ScriptFlowGraphRelation).where(ScriptFlowGraphRelation.agent_id == agent_id)
        )
    ).scalars().all()
    edges = []
    for r in rows:
        sid = _id_script_node(r.source_graph_node_id)
        tid = _id_script_node(r.target_graph_node_id)
        if sid not in visible_node_ids or tid not in visible_node_ids:
            continue
        edges.append({
            "source_graph_node_id": sid,
            "target_graph_node_id": tid,
            "relation_type": (r.relation_type or "связан").strip()[:80] or "связан",
            "weight": float(r.weight or 1.0),
            "origin_slice": "script_bridge",
        })
    return edges


# --- Запись в БД (полная замена структурного слоя; semantic не трогаем) ---

async def _replace_structured_layer(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    nodes: list[dict],
    relations: list[dict],
) -> None:
    # 1. Удалить старые узлы и рёбра ровно с тем же tier — но не семантические.
    await db.execute(
        delete(AgentUnifiedGraphRelation).where(
            AgentUnifiedGraphRelation.agent_id == agent_id,
            AgentUnifiedGraphRelation.provenance_tier == PROVENANCE,
        )
    )
    await db.execute(
        delete(AgentUnifiedGraphNode).where(
            AgentUnifiedGraphNode.agent_id == agent_id,
            AgentUnifiedGraphNode.provenance_tier == PROVENANCE,
        )
    )

    # 2. Вставить новые. ON CONFLICT (agent_id, graph_node_id) DO UPDATE — на всякий случай,
    #    если в семантическом слое были одноимённые ноды (но мы их и не создаём там).
    if nodes:
        node_payload = [
            {
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "origin_slice": n["origin_slice"],
                "graph_node_id": n["graph_node_id"],
                "entity_type": n["entity_type"],
                "title": (n["title"] or n["graph_node_id"])[:500],
                "description": n.get("description"),
                "domain_entity_id": n.get("domain_entity_id"),
                "properties": n.get("properties") or {},
                "provenance_tier": PROVENANCE,
            }
            for n in nodes
        ]
        stmt = pg_insert(AgentUnifiedGraphNode).values(node_payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["agent_id", "graph_node_id"],
            set_={
                "tenant_id": stmt.excluded.tenant_id,
                "origin_slice": stmt.excluded.origin_slice,
                "entity_type": stmt.excluded.entity_type,
                "title": stmt.excluded.title,
                "description": stmt.excluded.description,
                "domain_entity_id": stmt.excluded.domain_entity_id,
                "properties": stmt.excluded.properties,
                "provenance_tier": stmt.excluded.provenance_tier,
            },
        )
        await db.execute(stmt)

    if relations:
        await db.execute(
            pg_insert(AgentUnifiedGraphRelation).values([
                {
                    "tenant_id": tenant_id,
                    "agent_id": agent_id,
                    "origin_slice": r["origin_slice"],
                    "source_graph_node_id": r["source_graph_node_id"],
                    "target_graph_node_id": r["target_graph_node_id"],
                    "relation_type": r["relation_type"],
                    "weight": float(r.get("weight", 1.0)),
                    "properties": {},
                    "provenance_tier": PROVENANCE,
                }
                for r in relations
            ])
        )


# --- Точка входа ---

async def materialize_unified_graph(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
) -> MaterializeResult:
    log.info("unified_graph.materialize.start", agent_id=str(agent_id))

    specialists = await _build_specialists(db, agent_id)
    services = await _build_services(db, agent_id)
    categories = await _build_categories(db, agent_id)
    questions = await _build_questions(db, agent_id)
    dir_nodes, item_nodes = await _build_directory_items(db, agent_id)
    script_nodes = await _build_script_flow_nodes(db, agent_id)

    all_nodes = specialists + services + categories + questions + dir_nodes + item_nodes + script_nodes
    visible_ids = {n["graph_node_id"] for n in all_nodes}

    spec_service_edges = await _link_specialist_service(db, agent_id, visible_ids)
    service_cat_edges = await _link_service_category(db, agent_id, visible_ids)
    dir_item_edges = await _link_directory_items(db, agent_id, visible_ids)
    script_edges = await _link_script_flow_relations(db, agent_id, visible_ids)
    all_edges = spec_service_edges + service_cat_edges + dir_item_edges + script_edges

    by_type: dict[str, int] = {}
    for n in all_nodes:
        by_type[n["entity_type"]] = by_type.get(n["entity_type"], 0) + 1

    await _replace_structured_layer(
        db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        nodes=all_nodes,
        relations=all_edges,
    )
    await db.commit()

    log.info(
        "unified_graph.materialize.done",
        agent_id=str(agent_id),
        nodes=len(all_nodes),
        relations=len(all_edges),
        by_type=by_type,
    )
    return MaterializeResult(nodes=len(all_nodes), relations=len(all_edges), by_type=by_type)
