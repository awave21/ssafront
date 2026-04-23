"""
Wave 7: migrate flow_definition from schema_version 1 → 2.

Per-node shape changes are documented in the product roadmap (discriminated fields by node_type).
"""

from __future__ import annotations

import copy
import uuid
from typing import Any


def _str_list(val: Any) -> list[str]:
    if not isinstance(val, list):
        return []
    return [str(x).strip() for x in val if str(x).strip()]


def _migrate_node_data(
    data: dict[str, Any],
    *,
    flow_meta: dict[str, Any],
    audit_lines: list[str],
    node_id: str,
) -> dict[str, Any]:
    nt = str(data.get("node_type") or "expertise")

    if nt == "trigger":
        phrases = _str_list(data.get("client_phrase_examples")) or _str_list(data.get("example_phrases"))
        hints = _str_list(data.get("keyword_hints")) or _str_list(flow_meta.get("keyword_hints"))
        when_rel = (data.get("when_relevant") or data.get("situation") or "").strip()
        out: dict[str, Any] = {
            "node_type": "trigger",
            "client_phrase_examples": phrases,
            "keyword_hints": hints,
            "is_flow_entry": bool(data.get("is_flow_entry", data.get("is_entry_point", True))),
            "is_searchable": bool(data.get("is_searchable", data.get("is_entry_point", True))),
        }
        if data.get("title") is not None:
            out["title"] = data.get("title")
        if data.get("label") is not None:
            out["label"] = data.get("label")
        if when_rel:
            out["when_relevant"] = when_rel
        for legacy in ("approach", "watch_out", "good_question", "why_it_works"):
            v = data.get(legacy)
            if v and str(v).strip():
                audit_lines.append(f"node {node_id} (trigger): legacy `{legacy}` dropped (Wave 7)")
        return out

    if nt == "question":
        ex = _str_list(data.get("example_phrases"))
        gq = str(data.get("good_question") or "").strip()
        alts = [x for x in ex if x and x != gq]
        out = {
            "node_type": "question",
            "title": data.get("title"),
            "label": data.get("label"),
            "good_question": gq,
            "alternative_phrasings": alts,
            "expected_answer_type": str(data.get("expected_answer_type") or "open"),
            "why_we_ask": (data.get("why_we_ask") or data.get("situation") or "").strip() or None,
            "stage": data.get("stage"),
            "level": data.get("level"),
            "service_ids": data.get("service_ids") if isinstance(data.get("service_ids"), list) else [],
            "employee_ids": data.get("employee_ids") if isinstance(data.get("employee_ids"), list) else [],
            "is_searchable": bool(data.get("is_searchable", data.get("is_entry_point", True))),
            "kg_links": copy.deepcopy(data.get("kg_links") or {})
            if isinstance(data.get("kg_links"), dict)
            else {},
        }
        if data.get("expertise_axes"):
            out["expertise_axes"] = copy.deepcopy(data["expertise_axes"])
        for legacy in ("approach", "watch_out"):
            v = data.get(legacy)
            if v and str(v).strip():
                audit_lines.append(f"node {node_id} (question): removed `{legacy}`")
        return out

    if nt == "condition":
        conds = data.get("conditions")
        branches: list[dict[str, Any]] = []
        if isinstance(conds, list):
            for c in conds:
                if isinstance(c, dict) and str(c.get("id") or "").strip():
                    branches.append(
                        {"id": str(c["id"]).strip(), "label": str(c.get("label") or "").strip()}
                    )
                elif isinstance(c, dict):
                    bid = str(c.get("id") or "").strip() or str(uuid.uuid4())
                    branches.append(
                        {"id": bid, "label": str(c.get("label") or "").strip()}
                    )
                else:
                    branches.append({"id": str(uuid.uuid4()), "label": str(c).strip()})
        out = {
            "node_type": "condition",
            "title": data.get("title"),
            "label": data.get("label"),
            "routing_hint": (data.get("routing_hint") or data.get("situation") or "").strip() or None,
            "conditions": branches,
        }
        return out

    if nt == "goto":
        ex = _str_list(data.get("example_phrases"))
        out = {
            "node_type": "goto",
            "title": data.get("title"),
            "label": data.get("label"),
            "target_flow_id": str(data.get("target_flow_id") or "").strip() or "",
            "target_node_ref": data.get("target_node_ref"),
            "transition_phrase": (ex[0] if ex else None)
            or (data.get("transition_phrase") or "").strip()
            or None,
            "trigger_situation": (data.get("trigger_situation") or data.get("situation") or "").strip()
            or None,
        }
        return out

    if nt == "expertise":
        out = copy.deepcopy(data)
        out["node_type"] = "expertise"
        return out

    if nt == "end":
        out = copy.deepcopy(data)
        out["node_type"] = "end"
        return out

    if nt == "business_rule":
        out = copy.deepcopy(data)
        out["node_type"] = "business_rule"
        return out

    out = copy.deepcopy(data)
    out["node_type"] = nt
    return out


def migrate_flow_definition_to_v2(
    flow_definition: dict[str, Any],
    *,
    flow_metadata: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Returns new flow_definition dict (deep copy) and audit lines."""
    fd = copy.deepcopy(flow_definition) if flow_definition else {}
    audit_lines: list[str] = []
    meta = flow_metadata if isinstance(flow_metadata, dict) else {}

    nodes = fd.get("nodes")
    if not isinstance(nodes, list):
        fd["nodes"] = []
        nodes = fd["nodes"]

    new_nodes: list[dict[str, Any]] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "")
        node = copy.deepcopy(n)
        raw = node.get("data")
        if not isinstance(raw, dict):
            raw = {}
        node["data"] = _migrate_node_data(
            raw,
            flow_meta=meta,
            audit_lines=audit_lines,
            node_id=nid or "?",
        )
        new_nodes.append(node)

    fd["nodes"] = new_nodes
    fd["schema_version"] = 2
    return fd, audit_lines


def flow_has_invalid_goto(flow_definition: dict[str, Any]) -> bool:
    nodes = flow_definition.get("nodes") if isinstance(flow_definition, dict) else None
    if not isinstance(nodes, list):
        return False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        d = n.get("data")
        if not isinstance(d, dict):
            continue
        if d.get("node_type") != "goto":
            continue
        tf = str(d.get("target_flow_id") or "").strip()
        if not tf:
            return True
    return False
