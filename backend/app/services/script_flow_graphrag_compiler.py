from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.models.script_flow import ScriptFlow
from app.db.models.script_flow_graph_community import ScriptFlowGraphCommunity
from app.db.models.script_flow_graph_diagnostic import ScriptFlowGraphDiagnostic
from app.db.models.script_flow_graph_node import ScriptFlowGraphNode
from app.db.models.script_flow_graph_relation import ScriptFlowGraphRelation
from app.services.script_flow_graphrag_extractor import ScriptFlowGraphRAGExtractor
from app.services.script_flow_graphrag_schema import ScriptFlowGraphPreview
from app.services.script_flow_graphrag_store import ScriptFlowGraphRAGStore


@dataclass
class ScriptFlowGraphRAGPayload:
    nodes: list[ScriptFlowGraphNode]
    relations: list[ScriptFlowGraphRelation]
    communities: list[ScriptFlowGraphCommunity]
    diagnostic: ScriptFlowGraphDiagnostic | None
    preview: ScriptFlowGraphPreview


def _flow_topic_suffix(flow: ScriptFlow) -> str:
    fd = flow.flow_definition if isinstance(flow.flow_definition, dict) else {}
    nodes = fd.get("nodes") if isinstance(fd.get("nodes"), list) else []
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        data = n.get("data") if isinstance(n.get("data"), dict) else {}
        node_type = str(n.get("type") or data.get("nodeType") or "").lower().strip()
        if node_type != "trigger":
            continue
        kh: Any = data.get("keyword_hints")
        if isinstance(kh, list):
            kws = [str(k).strip() for k in kh if str(k).strip()]
            if kws:
                return ", ".join(kws[:2])
    return (flow.name or "").strip()


def _apply_topic_suffix(title: str | None, suffix: str) -> str:
    base = (title or "").strip()
    if not base:
        return ""
    if not suffix:
        return base
    return f"{base} · {suffix}"


def _build_canvas_stage_map(flow: ScriptFlow) -> dict[str, str]:
    fd = flow.flow_definition if isinstance(flow.flow_definition, dict) else {}
    nodes = fd.get("nodes") if isinstance(fd.get("nodes"), list) else []
    out: dict[str, str] = {}
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "").strip()
        data = n.get("data") if isinstance(n.get("data"), dict) else {}
        stage = str(data.get("stage") or "").strip()
        if nid and stage:
            out[nid] = stage
    return out


def _enrich_properties_with_stage(
    props: dict[str, Any] | None,
    source_node_ids: list[str] | None,
    stage_map: dict[str, str],
) -> dict[str, Any]:
    enriched = dict(props or {})
    if not stage_map or not source_node_ids:
        return enriched
    seen: set[str] = set()
    stages: list[str] = []
    for sid in source_node_ids:
        st = stage_map.get(str(sid))
        if st and st not in seen:
            seen.add(st)
            stages.append(st)
    if stages:
        enriched["stage_hint"] = ", ".join(stages)
    return enriched


async def compile_script_flow_graphrag_payload(
    flow: ScriptFlow,
    *,
    openai_api_key: str | None = None,
    extraction_model: str | None = None,
    summary_model: str | None = None,
) -> ScriptFlowGraphRAGPayload:
    extractor = ScriptFlowGraphRAGExtractor()
    entities, relations, debug = await extractor.extract(
        flow_definition=flow.flow_definition if isinstance(flow.flow_definition, dict) else {},
        flow_metadata=flow.flow_metadata if isinstance(flow.flow_metadata, dict) else {},
        flow_name=flow.name or None,
        openai_api_key=openai_api_key,
        model_name=extraction_model,
    )
    store = ScriptFlowGraphRAGStore()
    communities = await store.build_communities(
        nodes=entities,
        relations=relations,
        openai_api_key=openai_api_key,
        model_name=summary_model,
    )

    topic_suffix = _flow_topic_suffix(flow)
    stage_map = _build_canvas_stage_map(flow)
    node_rows = [
        ScriptFlowGraphNode(
            tenant_id=flow.tenant_id,
            agent_id=flow.agent_id,
            flow_id=flow.id,
            flow_version=int(flow.published_version or 0),
            graph_node_id=item.graph_node_id,
            node_kind=item.node_kind.value,
            entity_type=item.entity_type,
            title=_apply_topic_suffix(item.title, topic_suffix),
            description=item.description,
            source_node_ids=item.source_node_ids,
            properties=_enrich_properties_with_stage(item.properties, item.source_node_ids, stage_map),
            community_key=item.community_key,
        )
        for item in entities
    ]
    relation_rows = [
        ScriptFlowGraphRelation(
            tenant_id=flow.tenant_id,
            agent_id=flow.agent_id,
            flow_id=flow.id,
            flow_version=int(flow.published_version or 0),
            source_graph_node_id=item.source_graph_node_id,
            target_graph_node_id=item.target_graph_node_id,
            relation_type=item.relation_type,
            weight=item.weight,
            properties=item.properties,
        )
        for item in relations
    ]
    community_rows = [
        ScriptFlowGraphCommunity(
            tenant_id=flow.tenant_id,
            agent_id=flow.agent_id,
            flow_id=flow.id,
            flow_version=int(flow.published_version or 0),
            community_key=item.community_key,
            title=item.title,
            summary=item.summary,
            node_ids=item.node_ids,
            properties=item.properties,
        )
        for item in communities
    ]
    summary_llm_count = sum(
        1 for item in communities if (item.properties or {}).get("summary_source") == "llm"
    )
    summary_fallback_count = sum(
        1 for item in communities if (item.properties or {}).get("summary_source") != "llm"
    )
    diagnostic = ScriptFlowGraphDiagnostic(
        tenant_id=flow.tenant_id,
        agent_id=flow.agent_id,
        flow_id=flow.id,
        flow_version=int(flow.published_version or 0),
        extraction_model=extraction_model,
        summary_model=summary_model,
        extraction_mode=str(debug.get("extraction_mode") or ""),
        llm_ok_nodes=int(debug.get("llm_ok_nodes") or 0),
        llm_failed_nodes=int(debug.get("llm_failed_nodes") or 0),
        entity_count=int(debug.get("entity_count") or 0),
        relation_count=int(debug.get("relation_count") or 0),
        community_count=len(communities),
        summary_llm_count=summary_llm_count,
        summary_fallback_count=summary_fallback_count,
        debug=debug,
    )
    preview = ScriptFlowGraphPreview(
        flow_id=flow.id,
        flow_version=int(flow.published_version or 0),
        nodes=entities,
        relations=relations,
        communities=communities,
        debug=debug,
    )
    return ScriptFlowGraphRAGPayload(
        nodes=node_rows,
        relations=relation_rows,
        communities=community_rows,
        diagnostic=diagnostic,
        preview=preview,
    )
