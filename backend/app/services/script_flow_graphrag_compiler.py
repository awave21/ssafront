from __future__ import annotations

from dataclasses import dataclass

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

    node_rows = [
        ScriptFlowGraphNode(
            tenant_id=flow.tenant_id,
            agent_id=flow.agent_id,
            flow_id=flow.id,
            flow_version=int(flow.published_version or 0),
            graph_node_id=item.graph_node_id,
            node_kind=item.node_kind.value,
            entity_type=item.entity_type,
            title=item.title,
            description=item.description,
            source_node_ids=item.source_node_ids,
            properties=item.properties,
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
