from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.models.script_flow import ScriptFlow
from app.db.models.script_flow_edge_index import ScriptFlowEdgeIndex
from app.db.models.script_flow_node_index import ScriptFlowNodeIndex
from app.services.script_flow_compiler import (
    _branch_label_fallback,
    _condition_handle_map_from_data,
    _edge_label,
    _node_title,
    _node_type,
    _str,
    highlight_lookup_hints,
    substitute_flow_variables,
)


@dataclass
class ScriptFlowIndexPayload:
    nodes: list[ScriptFlowNodeIndex]
    edges: list[ScriptFlowEdgeIndex]


def _as_list_of_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        s = str(item).strip()
        if s:
            out.append(s)
    return out


def _truncate(value: Any, max_len: int) -> str:
    s = _str(value)
    if not s:
        return ""
    if len(s) <= max_len:
        return s
    return s[:max_len]


def _node_data(node: dict[str, Any]) -> dict[str, Any]:
    data = node.get("data")
    return data if isinstance(data, dict) else {}


def _render_node_content_text(data: dict[str, Any], variables: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in (
        "situation",
        "why_it_works",
        "approach",
        "good_question",
        "watch_out",
        "required_followup_question",
        "when_relevant",
        "why_we_ask",
        "routing_hint",
        "transition_phrase",
        "trigger_situation",
        "rule_condition",
        "rule_action",
    ):
        v = _str(data.get(key))
        if v:
            chunks.append(v)

    for key in (
        "example_phrases",
        "alternative_phrasings",
        "preferred_phrases",
        "forbidden_phrases",
        "client_phrase_examples",
        "keyword_hints",
    ):
        vals = _as_list_of_str(data.get(key))
        if vals:
            chunks.append("; ".join(vals))

    text = "\n".join(chunks).strip()
    if not text:
        return ""
    return highlight_lookup_hints(substitute_flow_variables(text, variables))


def _collect_node_filters(
    data: dict[str, Any],
    *,
    flow_metadata: dict[str, Any],
) -> dict[str, list[str]]:
    kg = data.get("kg_links") if isinstance(data.get("kg_links"), dict) else {}
    return {
        "service_ids": _as_list_of_str(data.get("service_ids"))
        or _as_list_of_str(flow_metadata.get("service_ids")),
        "employee_ids": _as_list_of_str(data.get("employee_ids"))
        or _as_list_of_str(flow_metadata.get("employee_ids")),
        "motive_ids": _as_list_of_str(kg.get("motive_ids")),
        "objection_ids": _as_list_of_str(kg.get("objection_ids")),
        "proof_ids": _as_list_of_str(kg.get("proof_ids")),
        "constraint_ids": _as_list_of_str(kg.get("constraint_ids")),
    }


def compile_script_flow_index_payload(flow: ScriptFlow) -> ScriptFlowIndexPayload:
    flow_definition = flow.flow_definition if isinstance(flow.flow_definition, dict) else {}
    flow_metadata = flow.flow_metadata if isinstance(flow.flow_metadata, dict) else {}
    variables = flow_metadata.get("variables") or {}

    nodes_raw = flow_definition.get("nodes")
    edges_raw = flow_definition.get("edges")
    nodes_list = nodes_raw if isinstance(nodes_raw, list) else []
    edges_list = edges_raw if isinstance(edges_raw, list) else []

    node_by_id: dict[str, dict[str, Any]] = {}
    for node in nodes_list:
        if isinstance(node, dict):
            nid = str(node.get("id") or "").strip()
            if nid:
                node_by_id[nid] = node

    node_indexes: list[ScriptFlowNodeIndex] = []
    for node_id, node in node_by_id.items():
        data = _node_data(node)
        node_type = _truncate(_node_type(node), 50)
        title = _truncate(_node_title(node), 255)
        stage_s = _truncate(data.get("stage"), 50)
        stage = stage_s or None
        content_text = _render_node_content_text(data, variables)
        filters = _collect_node_filters(data, flow_metadata=flow_metadata)
        is_searchable = data.get("is_searchable")
        if node_type == "condition":
            # Legacy flow JSON often persisted condition nodes with
            # is_searchable=false even though their content is required for
            # retrieval. Treat condition nodes as searchable by default.
            is_searchable = True
        elif not isinstance(is_searchable, bool):
            is_searchable = node_type in {"trigger", "expertise", "question"}

        node_indexes.append(
            ScriptFlowNodeIndex(
                tenant_id=flow.tenant_id,
                agent_id=flow.agent_id,
                flow_id=flow.id,
                flow_version=int(flow.published_version or 0),
                node_id=_truncate(node_id, 120),
                node_type=node_type,
                stage=stage,
                title=title,
                content_text=content_text or title,
                service_ids=filters["service_ids"],
                employee_ids=filters["employee_ids"],
                motive_ids=filters["motive_ids"],
                objection_ids=filters["objection_ids"],
                proof_ids=filters["proof_ids"],
                constraint_ids=filters["constraint_ids"],
                required_followup_question=_str(data.get("required_followup_question")) or None,
                communication_style=_truncate(data.get("communication_style"), 100) or None,
                preferred_phrases=_as_list_of_str(data.get("preferred_phrases")),
                forbidden_phrases=_as_list_of_str(data.get("forbidden_phrases")),
                is_searchable=is_searchable,
            )
        )

    edge_indexes: list[ScriptFlowEdgeIndex] = []
    for edge in edges_list:
        if not isinstance(edge, dict):
            continue
        source_node_id = str(edge.get("source") or "").strip()
        target_node_id = str(edge.get("target") or "").strip()
        if not source_node_id or not target_node_id:
            continue
        source_handle = str(
            edge.get("sourceHandle") or edge.get("source_handle") or ""
        ).strip()
        source_data = _node_data(node_by_id.get(source_node_id, {}))
        branch_label = _edge_label(edge).strip()
        if not branch_label and _node_type(node_by_id.get(source_node_id, {})) == "condition":
            handle_map = _condition_handle_map_from_data(source_data)
            branch_label = (
                handle_map.get(source_handle)
                or (_branch_label_fallback(source_handle) if source_handle else "")
            )

        edge_indexes.append(
            ScriptFlowEdgeIndex(
                tenant_id=flow.tenant_id,
                agent_id=flow.agent_id,
                flow_id=flow.id,
                source_node_id=_truncate(source_node_id, 120),
                target_node_id=_truncate(target_node_id, 120),
                source_handle=_truncate(source_handle, 120) or None,
                branch_label=_truncate(branch_label, 255) or None,
            )
        )

    return ScriptFlowIndexPayload(nodes=node_indexes, edges=edge_indexes)
