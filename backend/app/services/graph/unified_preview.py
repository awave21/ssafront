"""Unified-graph preview backed by Neo4j.

UI-эндпоинт /unified-graph/preview зеркалит ровно тот граф, который видит
runtime-агент через HybridGraphRetriever: :FlowNode/:GraphNode/:Service/:Specialist.

Это позволяет инженеру отлаживать graphRAG-ответы LLM, видя реальное
содержимое графа.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.services.runtime.neo4j_client import get_neo4j_driver

logger = structlog.get_logger(__name__)


# Mapping label → origin_slice (используется фронтом для кластеризации/цвета)
_ORIGIN_BY_LABEL: dict[str, str] = {
    "FlowNode": "script_canvas",
    "GraphNode": "script_bridge",
    "Service": "sqns",
    "Specialist": "sqns",
}

_TYPE_BY_LABEL: dict[str, str] = {
    "Service": "service",
    "Specialist": "specialist",
}

_DETERMINISTIC_RELATION_TYPES = {"NEXT_STEP_TO", "PROVIDED_BY", "HAS_SEMANTIC"}

_LLM_SOURCES = {"llm_structured_extraction"}


def _safe_json_loads(value: Any) -> dict[str, Any]:
    """Properties в Neo4j хранятся как JSON-строка (Map недоступен)."""
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def _build_node_id(label: str, props: dict[str, Any]) -> str | None:
    """API ID для UI: префиксирован, чтобы избежать коллизий между типами."""
    if label == "FlowNode":
        nid = props.get("node_id")
        return f"flow:{nid}" if nid else None
    if label == "GraphNode":
        # graph_node_id уже префиксированный (canvas:n1 / objection:foo / stage:s)
        gid = props.get("graph_node_id")
        return str(gid) if gid else None
    if label == "Service":
        ext = props.get("external_id")
        return f"service:{ext}" if ext is not None else None
    if label == "Specialist":
        ext = props.get("external_id")
        return f"specialist:{ext}" if ext is not None else None
    return None


def _node_to_dto(label: str, props: dict[str, Any]) -> dict[str, Any] | None:
    node_id = _build_node_id(label, props)
    if not node_id:
        return None

    # entity_type
    if label in _TYPE_BY_LABEL:
        entity_type = _TYPE_BY_LABEL[label]
    elif label == "FlowNode":
        entity_type = props.get("node_type") or "script_node"
    else:  # GraphNode
        entity_type = props.get("entity_type") or "entity"

    # description
    if label == "FlowNode":
        description = (props.get("content_text") or props.get("title") or "")
    elif label == "GraphNode":
        description = props.get("description") or ""
    elif label == "Service":
        description = props.get("description") or ""
    elif label == "Specialist":
        description = props.get("specialization") or props.get("information") or ""
    else:
        description = ""

    label_text = props.get("title") or props.get("name") or node_id

    return {
        "id": node_id,
        "label": label_text,
        "type": entity_type,
        "description": description,
        "origin_slice": _ORIGIN_BY_LABEL.get(label, "unknown"),
        "provenance_tier": "structured",
        "properties": _safe_json_loads(props.get("properties")),
    }


def _relation_provenance(rel_type: str, rel_props: dict[str, Any]) -> str:
    """Маппинг relation → provenance_tier.

    Все детерминированные рёбра — structured. GRAPH_RELATION со source=llm_structured_extraction
    из properties — semantic.
    """
    if rel_type in _DETERMINISTIC_RELATION_TYPES:
        return "structured"
    inner_props = _safe_json_loads(rel_props.get("properties"))
    src_field = (inner_props.get("source") or "").strip()
    if src_field in _LLM_SOURCES:
        return "semantic"
    return "structured"


def _neo4j_node_to_id(neo4j_node: Any) -> str | None:
    """Reconstruct DTO node-id from a Neo4j node by inspecting its labels."""
    if not neo4j_node:
        return None
    labels = list(getattr(neo4j_node, "labels", []) or [])
    target_label = next((l for l in labels if l in _ORIGIN_BY_LABEL), None)
    if not target_label:
        return None
    return _build_node_id(target_label, dict(neo4j_node))


def _query_neo4j_sync(
    *,
    agent_id_str: str,
    tenant_id_str: str,
    node_limit: int,
    edge_limit: int,
    database: str | None,
) -> dict[str, Any]:
    """Sync-запрос в Neo4j. Вызывается через run_in_executor."""
    driver = get_neo4j_driver()
    if driver is None:
        return {
            "nodes": [],
            "relations": [],
            "node_count": 0,
            "edge_count": 0,
            "truncated": False,
            "preview_source": "neo4j_unavailable",
            "preview_error": "Neo4j driver not available",
            "message": "Neo4j отключён или недоступен.",
        }

    nodes_cypher = """
    MATCH (n)
    WHERE n.agent_id = $agent_id
      AND n.tenant_id = $tenant_id
      AND any(l IN labels(n) WHERE l IN ['FlowNode','GraphNode','Service','Specialist'])
    WITH n, [l IN labels(n) WHERE l IN ['FlowNode','GraphNode','Service','Specialist']][0] AS lab
    RETURN n AS node, lab AS label
    LIMIT $node_limit
    """

    rels_cypher = """
    MATCH (s)-[r]->(t)
    WHERE s.agent_id = $agent_id
      AND s.tenant_id = $tenant_id
      AND t.agent_id = $agent_id
      AND any(l IN labels(s) WHERE l IN ['FlowNode','GraphNode','Service','Specialist'])
      AND any(l IN labels(t) WHERE l IN ['FlowNode','GraphNode','Service','Specialist'])
    RETURN s AS src, t AS tgt, type(r) AS rel_type, properties(r) AS rel_props,
           id(r) AS rel_id
    LIMIT $edge_limit
    """

    nodes_dto: list[dict[str, Any]] = []
    relations_dto: list[dict[str, Any]] = []
    node_count = 0
    edge_count = 0

    with driver.session(database=database) as session:
        # Total counts (cheap)
        total_nodes_row = session.run(
            """
            MATCH (n)
            WHERE n.agent_id = $agent_id AND n.tenant_id = $tenant_id
              AND any(l IN labels(n) WHERE l IN ['FlowNode','GraphNode','Service','Specialist'])
            RETURN count(n) AS c
            """,
            agent_id=agent_id_str,
            tenant_id=tenant_id_str,
        ).single()
        node_count = int(total_nodes_row["c"]) if total_nodes_row else 0

        total_edges_row = session.run(
            """
            MATCH (s)-[r]->(t)
            WHERE s.agent_id = $agent_id AND s.tenant_id = $tenant_id
              AND t.agent_id = $agent_id
              AND any(l IN labels(s) WHERE l IN ['FlowNode','GraphNode','Service','Specialist'])
              AND any(l IN labels(t) WHERE l IN ['FlowNode','GraphNode','Service','Specialist'])
            RETURN count(r) AS c
            """,
            agent_id=agent_id_str,
            tenant_id=tenant_id_str,
        ).single()
        edge_count = int(total_edges_row["c"]) if total_edges_row else 0

        # Fetch nodes
        for row in session.run(
            nodes_cypher,
            agent_id=agent_id_str,
            tenant_id=tenant_id_str,
            node_limit=int(node_limit),
        ):
            label = row["label"]
            props = dict(row["node"])
            dto = _node_to_dto(label, props)
            if dto:
                nodes_dto.append(dto)

        visible_ids = {n["id"] for n in nodes_dto}

        # Fetch edges; skip those whose endpoints aren't in the visible set.
        for row in session.run(
            rels_cypher,
            agent_id=agent_id_str,
            tenant_id=tenant_id_str,
            edge_limit=int(edge_limit),
        ):
            src_id = _neo4j_node_to_id(row["src"])
            tgt_id = _neo4j_node_to_id(row["tgt"])
            if not src_id or not tgt_id:
                continue
            if src_id not in visible_ids or tgt_id not in visible_ids:
                continue
            rel_type = row["rel_type"]
            rel_props = row["rel_props"] or {}
            relations_dto.append({
                "id": str(row["rel_id"]),
                "source": src_id,
                "target": tgt_id,
                "label": rel_type,
                "weight": float(rel_props.get("weight") or 1.0),
                "origin_slice": "neo4j",
                "provenance_tier": _relation_provenance(rel_type, rel_props),
            })

    return {
        "nodes": nodes_dto,
        "relations": relations_dto,
        "node_count": node_count,
        "edge_count": edge_count,
        "truncated": node_count > len(nodes_dto) or edge_count > len(relations_dto),
        "preview_source": "neo4j",
        "preview_error": None,
        "message": None if nodes_dto else "Граф ещё не построен — нажмите «Пересобрать граф».",
    }


async def load_unified_graph_from_neo4j(
    *,
    agent_id: UUID,
    tenant_id: UUID,
    node_limit: int = 2000,
    edge_limit: int = 6000,
) -> dict[str, Any]:
    """Async-обёртка над sync neo4j-driver. Не блокирует event loop."""
    settings = get_settings()
    if not settings.neo4j_enabled:
        return {
            "nodes": [],
            "relations": [],
            "node_count": 0,
            "edge_count": 0,
            "truncated": False,
            "preview_source": "neo4j_disabled",
            "preview_error": None,
            "message": "Neo4j выключен в конфиге (NEO4J_ENABLED=false).",
        }

    database = settings.neo4j_database or None

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(
            None,
            lambda: _query_neo4j_sync(
                agent_id_str=str(agent_id),
                tenant_id_str=str(tenant_id),
                node_limit=node_limit,
                edge_limit=edge_limit,
                database=database,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "unified_graph_neo4j_read_failed",
            agent_id=str(agent_id),
            error=str(exc),
        )
        return {
            "nodes": [],
            "relations": [],
            "node_count": 0,
            "edge_count": 0,
            "truncated": False,
            "preview_source": "neo4j_error",
            "preview_error": str(exc),
            "message": f"Ошибка чтения Neo4j: {exc}",
        }
