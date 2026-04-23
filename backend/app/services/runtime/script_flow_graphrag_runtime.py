from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.script_flow_graph_community import ScriptFlowGraphCommunity
from app.db.models.script_flow_graph_node import ScriptFlowGraphNode
from app.db.models.script_flow_graph_relation import ScriptFlowGraphRelation


async def enrich_matches_with_graph_context(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    matches: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Hydrate node-retrieval matches with stored GraphRAG entities/communities."""
    if not matches:
        return matches, {
            "graph_enrichment_used": False,
            "matched_graph_nodes": 0,
            "matched_communities": 0,
        }

    pairs: list[tuple[str, str]] = []
    flow_ids: set[UUID] = set()
    for match in matches:
        flow_raw = str(match.get("flow_id") or "").strip()
        node_ref = str(match.get("tactic_node_ref") or "").strip()
        if not flow_raw or not node_ref:
            continue
        try:
            fid = UUID(flow_raw)
        except ValueError:
            continue
        flow_ids.add(fid)
        pairs.append((str(fid), node_ref))

    if not pairs or not flow_ids:
        return matches, {
            "graph_enrichment_used": False,
            "matched_graph_nodes": 0,
            "matched_communities": 0,
        }

    graph_rows = (
        await db.execute(
            select(ScriptFlowGraphNode).where(
                ScriptFlowGraphNode.tenant_id == tenant_id,
                ScriptFlowGraphNode.agent_id == agent_id,
                ScriptFlowGraphNode.flow_id.in_(flow_ids),
            )
        )
    ).scalars().all()

    matched_graph_nodes_by_pair: dict[tuple[str, str], list[ScriptFlowGraphNode]] = defaultdict(list)
    community_keys: set[str] = set()
    graph_node_ids: set[str] = set()
    for row in graph_rows:
        src_ids = [str(v).strip() for v in (row.source_node_ids or []) if str(v).strip()]
        if not src_ids:
            continue
        for flow_id_str, node_ref in pairs:
            if str(row.flow_id) != flow_id_str:
                continue
            if node_ref in src_ids:
                matched_graph_nodes_by_pair[(flow_id_str, node_ref)].append(row)
                graph_node_ids.add(row.graph_node_id)
                if row.community_key:
                    community_keys.add(row.community_key)

    relation_rows: list[ScriptFlowGraphRelation] = []
    if graph_node_ids:
        relation_rows = list(
            (
                await db.execute(
                    select(ScriptFlowGraphRelation).where(
                        ScriptFlowGraphRelation.tenant_id == tenant_id,
                        ScriptFlowGraphRelation.agent_id == agent_id,
                        ScriptFlowGraphRelation.flow_id.in_(flow_ids),
                        ScriptFlowGraphRelation.source_graph_node_id.in_(graph_node_ids),
                    )
                )
            ).scalars().all()
        )

    target_ids = {str(r.target_graph_node_id) for r in relation_rows}
    linked_target_nodes: dict[str, ScriptFlowGraphNode] = {}
    if target_ids:
        target_rows = (
            await db.execute(
                select(ScriptFlowGraphNode).where(
                    ScriptFlowGraphNode.tenant_id == tenant_id,
                    ScriptFlowGraphNode.agent_id == agent_id,
                    ScriptFlowGraphNode.flow_id.in_(flow_ids),
                    ScriptFlowGraphNode.graph_node_id.in_(target_ids),
                )
            )
        ).scalars().all()
        linked_target_nodes = {str(row.graph_node_id): row for row in target_rows}
        for row in target_rows:
            if row.community_key:
                community_keys.add(row.community_key)

    community_by_key: dict[str, ScriptFlowGraphCommunity] = {}
    if community_keys:
        community_rows = (
            await db.execute(
                select(ScriptFlowGraphCommunity).where(
                    ScriptFlowGraphCommunity.tenant_id == tenant_id,
                    ScriptFlowGraphCommunity.agent_id == agent_id,
                    ScriptFlowGraphCommunity.flow_id.in_(flow_ids),
                    ScriptFlowGraphCommunity.community_key.in_(community_keys),
                )
            )
        ).scalars().all()
        community_by_key = {str(row.community_key): row for row in community_rows}

    outgoing_by_source: dict[str, list[ScriptFlowGraphRelation]] = defaultdict(list)
    for rel in relation_rows:
        outgoing_by_source[str(rel.source_graph_node_id)].append(rel)

    enriched: list[dict[str, Any]] = []
    used_communities: set[str] = set()
    for match in matches:
        flow_id_str = str(match.get("flow_id") or "").strip()
        node_ref = str(match.get("tactic_node_ref") or "").strip()
        graph_nodes = matched_graph_nodes_by_pair.get((flow_id_str, node_ref), [])
        out = dict(match)

        motive_names = set(str(v).strip() for v in (out.get("motive_names") or []) if str(v).strip())
        argument_names = set(str(v).strip() for v in (out.get("argument_names") or []) if str(v).strip())
        proof_names = set(str(v).strip() for v in (out.get("proof_names") or []) if str(v).strip())
        objection_names = set(str(v).strip() for v in (out.get("objection_names") or []) if str(v).strip())
        constraint_names = set(str(v).strip() for v in (out.get("constraint_names") or []) if str(v).strip())
        graph_entity_titles: set[str] = set()
        graph_relation_types: set[str] = set()
        community_summaries: list[dict[str, Any]] = []

        for gnode in graph_nodes:
            if gnode.entity_type == "motive":
                motive_names.add(gnode.title)
            elif gnode.entity_type == "argument":
                argument_names.add(gnode.title)
            elif gnode.entity_type == "proof":
                proof_names.add(gnode.title)
            elif gnode.entity_type == "objection":
                objection_names.add(gnode.title)
            elif gnode.entity_type == "constraint":
                constraint_names.add(gnode.title)
            elif gnode.entity_type not in {"stage", "variable", "trigger", "question", "expertise", "condition", "goto", "business_rule", "end"}:
                graph_entity_titles.add(gnode.title)

            if gnode.community_key and gnode.community_key in community_by_key:
                community = community_by_key[gnode.community_key]
                used_communities.add(gnode.community_key)
                community_summaries.append(
                    {
                        "community_key": community.community_key,
                        "title": community.title,
                        "summary": community.summary,
                        "size": (community.properties or {}).get("size"),
                        "key_points": (community.properties or {}).get("key_points") or [],
                        "recommended_next_step": (community.properties or {}).get("recommended_next_step"),
                    }
                )

            for rel in outgoing_by_source.get(str(gnode.graph_node_id), []):
                graph_relation_types.add(rel.relation_type)
                target = linked_target_nodes.get(str(rel.target_graph_node_id))
                if target is None:
                    continue
                if target.entity_type == "motive":
                    motive_names.add(target.title)
                elif target.entity_type == "argument":
                    argument_names.add(target.title)
                elif target.entity_type == "proof":
                    proof_names.add(target.title)
                elif target.entity_type == "objection":
                    objection_names.add(target.title)
                elif target.entity_type == "constraint":
                    constraint_names.add(target.title)
                elif target.entity_type not in {"stage", "variable"}:
                    graph_entity_titles.add(target.title)

        dedup_communities: list[dict[str, Any]] = []
        seen_ck: set[str] = set()
        for item in community_summaries:
            ck = str(item.get("community_key") or "")
            if not ck or ck in seen_ck:
                continue
            seen_ck.add(ck)
            dedup_communities.append(item)

        out["motive_names"] = sorted(motive_names)
        out["argument_names"] = sorted(argument_names)
        out["proof_names"] = sorted(proof_names)
        out["objection_names"] = sorted(objection_names)
        out["constraint_names"] = sorted(constraint_names)
        out["graph_entities"] = sorted(graph_entity_titles)
        out["graph_relation_types"] = sorted(graph_relation_types)
        out["graph_communities"] = dedup_communities
        if dedup_communities:
            top_community = dedup_communities[0]
            out["community_title"] = top_community.get("title")
            out["community_summary"] = top_community.get("summary")
            out["recommended_next_step"] = top_community.get("recommended_next_step")

        enriched.append(out)

    return enriched, {
        "graph_enrichment_used": True,
        "matched_graph_nodes": sum(len(v) for v in matched_graph_nodes_by_pair.values()),
        "matched_communities": len(used_communities),
    }
