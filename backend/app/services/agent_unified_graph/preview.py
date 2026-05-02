"""Чтение unified-графа из БД для эндпоинта /preview.

Формат ответа совместим с тем, что раньше отдавал GraphRAG-parquet превью:
{nodes:[{id,label,type,description}], relations:[{id,source,target,label}]}.
Дополнительно отдаём origin_slice и provenance_tier для фронтовой стилизации.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_unified_graph_node import AgentUnifiedGraphNode
from app.db.models.agent_unified_graph_relation import AgentUnifiedGraphRelation

NODE_LIMIT_DEFAULT = 2000
EDGE_LIMIT_DEFAULT = 6000


async def load_unified_graph_preview(
    db: AsyncSession,
    *,
    agent_id: UUID,
    node_limit: int = NODE_LIMIT_DEFAULT,
    edge_limit: int = EDGE_LIMIT_DEFAULT,
) -> dict[str, object]:
    total_nodes = (
        await db.execute(
            select(func.count(AgentUnifiedGraphNode.id)).where(
                AgentUnifiedGraphNode.agent_id == agent_id
            )
        )
    ).scalar_one()

    total_edges = (
        await db.execute(
            select(func.count(AgentUnifiedGraphRelation.id)).where(
                AgentUnifiedGraphRelation.agent_id == agent_id
            )
        )
    ).scalar_one()

    if not total_nodes:
        return {
            "nodes": [],
            "relations": [],
            "node_count": 0,
            "edge_count": 0,
            "truncated": False,
            "preview_source": "unified_graph_empty",
            "preview_error": None,
            "message": "Граф ещё не построен — нажмите «Пересобрать граф».",
        }

    nodes_rows = (
        await db.execute(
            select(AgentUnifiedGraphNode)
            .where(AgentUnifiedGraphNode.agent_id == agent_id)
            .order_by(AgentUnifiedGraphNode.entity_type, AgentUnifiedGraphNode.title)
            .limit(node_limit)
        )
    ).scalars().all()
    visible_ids = {n.graph_node_id for n in nodes_rows}

    edges_rows = (
        await db.execute(
            select(AgentUnifiedGraphRelation)
            .where(
                AgentUnifiedGraphRelation.agent_id == agent_id,
                AgentUnifiedGraphRelation.source_graph_node_id.in_(visible_ids),
                AgentUnifiedGraphRelation.target_graph_node_id.in_(visible_ids),
            )
            .limit(edge_limit)
        )
    ).scalars().all()

    nodes = [
        {
            "id": n.graph_node_id,
            "label": n.title or n.graph_node_id,
            "type": n.entity_type,
            "description": n.description or "",
            "origin_slice": n.origin_slice,
            "provenance_tier": n.provenance_tier,
        }
        for n in nodes_rows
    ]
    relations = [
        {
            "id": str(r.id),
            "source": r.source_graph_node_id,
            "target": r.target_graph_node_id,
            "label": r.relation_type,
            "weight": float(r.weight or 1.0),
            "origin_slice": r.origin_slice,
            "provenance_tier": r.provenance_tier,
        }
        for r in edges_rows
    ]

    return {
        "nodes": nodes,
        "relations": relations,
        "node_count": int(total_nodes),
        "edge_count": int(total_edges),
        "truncated": int(total_nodes) > len(nodes) or int(total_edges) > len(relations),
        "preview_source": "unified_graph_db",
        "preview_error": None,
        "message": None,
    }
