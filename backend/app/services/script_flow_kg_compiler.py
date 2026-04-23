"""
script_flow_kg_compiler.py

Компилирует ScriptFlow (Vue Flow JSON) в структуру, пригодную для
legacy custom-KG insert pipeline — набор entities + relationships + chunks.

Философия:
- Каждый узел потока → одна KG-сущность.
- Явные ссылки эксперта (`data.kg_links.*`, `service_ids`, `employee_ids`,
  `constraints.must_follow_node_refs`) становятся custom-KG рёбрами с
  заданными keywords и weight.
- Тексты узлов попадают в `chunks[]` одним-per-node для автоэкстракции
  синонимов и связанных понятий в graph retrieval.
- Все записи помечены `source_id = "flow:<uuid>"` — это позволяет удалять
  прошлую версию потока перед переиндексацией.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID

from app.services.script_flow_compiler import (
    highlight_lookup_hints,
    substitute_flow_variables,
)

if TYPE_CHECKING:  # pragma: no cover — только аннотации
    from app.db.models.agent_kg_entity import AgentKgEntity
    from app.db.models.script_flow import ScriptFlow


# ── Helpers ──────────────────────────────────────────────────────────────────


def _str(v: Any, fallback: str = "") -> str:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return fallback


def _node_entity_name(flow_id: str, node_ref: str) -> str:
    return f"flow:{flow_id}#node:{node_ref}"


def _library_entity_name(entity_type: str, entity_id: str) -> str:
    return f"kg:{entity_type}:{entity_id}"


def _service_entity_name(service_id: str) -> str:
    return f"svc:{service_id}"


def _employee_entity_name(employee_id: str) -> str:
    return f"emp:{employee_id}"


def _render_node_chunk(
    *,
    node: dict[str, Any],
    variables: dict[str, Any],
) -> str:
    """Собирает короткий человекочитаемый чанк для одного узла.

    Используется для custom-KG `insert_custom_kg({"chunks":[...]})` — от
    compiled_text отличается тем, что всегда один узел = один чанк.
    """
    data = node.get("data") if isinstance(node.get("data"), dict) else {}

    def _v(t: str) -> str:
        return highlight_lookup_hints(substitute_flow_variables(t, variables or {}))

    parts: list[str] = []
    title = _str(data.get("title")) or _str(data.get("label")) or _str(node.get("id")) or "Шаг"
    ntype = _str(data.get("node_type"))
    stage = _str(data.get("stage"))
    parts.append(f"# {title}")
    if ntype:
        parts.append(f"type: {ntype}" + (f" · stage: {stage}" if stage else ""))

    for key, heading in (
        ("situation", "Ситуация/возражение"),
        ("why_it_works", "Мотив (психология)"),
        ("approach", "Аргументы/тактика"),
        ("watch_out", "Табу"),
        ("good_question", "Обязательный вопрос"),
        ("rule_condition", "Условие правила"),
        ("rule_action", "Действие правила"),
        ("final_action", "Финальное действие"),
    ):
        v = _str(data.get(key))
        if v:
            parts.append(f"{heading}: {_v(v)}")

    phrases = data.get("example_phrases")
    if isinstance(phrases, list):
        clean = [str(p).strip() for p in phrases if str(p).strip()]
        if clean:
            parts.append("Примеры фраз:\n" + "\n".join(f"- «{_v(p)}»" for p in clean))

    return "\n".join(parts)


def _node_description(node: dict[str, Any], variables: dict[str, Any]) -> str:
    """Короткое описание сущности-узла для graph retrieval."""
    data = node.get("data") if isinstance(node.get("data"), dict) else {}

    def _v(t: str) -> str:
        return highlight_lookup_hints(substitute_flow_variables(t, variables or {}))

    bits: list[str] = []
    for key in ("situation", "approach", "good_question", "rule_condition", "rule_action"):
        v = _str(data.get(key))
        if v:
            bits.append(_v(v))
        if len(bits) >= 3:
            break
    desc = " | ".join(bits) if bits else _str(data.get("title")) or "Узел потока"
    return desc[:500]


def _collect_ids(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x) for x in v if isinstance(x, str) and x.strip()]


def _iter_unique_add(
    dst: list[dict[str, Any]],
    seen: set[tuple[str, ...]],
    key: tuple[str, ...],
    value: dict[str, Any],
) -> None:
    if key in seen:
        return
    seen.add(key)
    dst.append(value)


# ── Public API ───────────────────────────────────────────────────────────────


def compile_script_flow_to_custom_kg(
    *,
    flow: "ScriptFlow",
    library_entities: "Iterable[AgentKgEntity]",
) -> dict[str, list[dict[str, Any]]]:
    """Возвращает словарь в формате `insert_custom_kg`:

    ```
    {
      "entities":      [{"entity_name":..,"entity_type":..,"description":..,"source_id":..,"file_path":..}],
      "relationships": [{"src_id":..,"tgt_id":..,"description":..,"keywords":..,"weight":..,"source_id":..,"file_path":..}],
      "chunks":        [{"content":..,"source_id":..,"file_path":..}],
    }
    ```
    """
    flow_id = str(flow.id)
    source_id = f"flow:{flow_id}"
    file_path = f"script_flow:{flow_id}"

    flow_def = flow.flow_definition if isinstance(flow.flow_definition, dict) else {}
    meta = flow.flow_metadata if isinstance(flow.flow_metadata, dict) else {}
    variables = meta.get("variables") or {}

    raw_nodes = flow_def.get("nodes") if isinstance(flow_def.get("nodes"), list) else []
    raw_edges = flow_def.get("edges") if isinstance(flow_def.get("edges"), list) else []

    nodes_by_id: dict[str, dict[str, Any]] = {}
    for n in raw_nodes:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if isinstance(nid, str):
            nodes_by_id[nid] = n

    lib_by_id: dict[str, AgentKgEntity] = {str(e.id): e for e in library_entities}

    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    seen_entities: set[tuple[str, ...]] = set()
    seen_relations: set[tuple[str, ...]] = set()

    flow_title = _str(flow.name, "Сценарий")

    # ── Flow-level root entity ───────────────────────────────────────────────
    flow_entity_name = f"flow:{flow_id}"
    _iter_unique_add(
        entities,
        seen_entities,
        ("entity", flow_entity_name),
        {
            "entity_name": flow_entity_name,
            "entity_type": "flow",
            "description": f"Сценарий продаж эксперта: {flow_title}",
            "source_id": source_id,
            "file_path": file_path,
        },
    )

    # ── Nodes → entities + chunks ────────────────────────────────────────────
    for node_id, node in nodes_by_id.items():
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        node_ref = _str(data.get("title")) or _str(data.get("label")) or node_id
        ent_name = _node_entity_name(flow_id, node_ref)
        ntype = _str(data.get("node_type")) or _str(node.get("type")) or "expertise"

        _iter_unique_add(
            entities,
            seen_entities,
            ("entity", ent_name),
            {
                "entity_name": ent_name,
                "entity_type": f"script_{ntype}",
                "description": _node_description(node, variables),
                "source_id": source_id,
                "file_path": file_path,
            },
        )

        # Flow → node: belongs_to
        _iter_unique_add(
            relationships,
            seen_relations,
            ("rel", flow_entity_name, ent_name, "contains"),
            {
                "src_id": flow_entity_name,
                "tgt_id": ent_name,
                "description": f"Узел входит в сценарий «{flow_title}»",
                "keywords": "contains node flow",
                "weight": 0.5,
                "source_id": source_id,
                "file_path": file_path,
            },
        )

        chunk_text = _render_node_chunk(node=node, variables=variables)
        if chunk_text.strip():
            chunks.append(
                {
                    "content": chunk_text,
                    "source_id": source_id,
                    "file_path": file_path,
                }
            )

        # ── kg_links → relationships to library entities ─────────────────────
        kg_links = data.get("kg_links") if isinstance(data.get("kg_links"), dict) else {}
        link_specs = (
            ("motive_ids", "motive", "motivated_by"),
            ("argument_ids", "argument", "argues_with"),
            ("proof_ids", "proof", "evidenced_by"),
            ("objection_ids", "objection", "answers"),
            ("constraint_ids", "constraint", "constrained_by"),
        )
        for field, etype, rel_kw in link_specs:
            for entity_id in _collect_ids(kg_links.get(field)):
                lib = lib_by_id.get(entity_id)
                if lib is None:
                    continue
                lib_name = _library_entity_name(etype, entity_id)
                _iter_unique_add(
                    entities,
                    seen_entities,
                    ("entity", lib_name),
                    {
                        "entity_name": lib_name,
                        "entity_type": etype,
                        "description": (_str(lib.description) or _str(lib.name) or etype)[:500],
                        "source_id": source_id,
                        "file_path": file_path,
                    },
                )
                _iter_unique_add(
                    relationships,
                    seen_relations,
                    ("rel", ent_name, lib_name, rel_kw),
                    {
                        "src_id": ent_name,
                        "tgt_id": lib_name,
                        "description": f"{rel_kw}: {lib.name}",
                        "keywords": rel_kw,
                        "weight": 1.5,
                        "source_id": source_id,
                        "file_path": file_path,
                    },
                )

        # outcome_id
        outcome_id = kg_links.get("outcome_id") if isinstance(kg_links, dict) else None
        if isinstance(outcome_id, str) and outcome_id:
            lib = lib_by_id.get(outcome_id)
            if lib is not None:
                out_name = _library_entity_name("outcome", outcome_id)
                _iter_unique_add(
                    entities,
                    seen_entities,
                    ("entity", out_name),
                    {
                        "entity_name": out_name,
                        "entity_type": "outcome",
                        "description": (_str(lib.description) or _str(lib.name) or "outcome")[:500],
                        "source_id": source_id,
                        "file_path": file_path,
                    },
                )
                _iter_unique_add(
                    relationships,
                    seen_relations,
                    ("rel", ent_name, out_name, "ends_in"),
                    {
                        "src_id": ent_name,
                        "tgt_id": out_name,
                        "description": f"Итог ветки: {lib.name}",
                        "keywords": "ends_in outcome",
                        "weight": 1.0,
                        "source_id": source_id,
                        "file_path": file_path,
                    },
                )

        # service_ids / employee_ids
        for sid in _collect_ids(data.get("service_ids")):
            svc_name = _service_entity_name(sid)
            _iter_unique_add(
                entities,
                seen_entities,
                ("entity", svc_name),
                {
                    "entity_name": svc_name,
                    "entity_type": "service",
                    "description": f"SQNS service id={sid}",
                    "source_id": source_id,
                    "file_path": file_path,
                },
            )
            _iter_unique_add(
                relationships,
                seen_relations,
                ("rel", ent_name, svc_name, "applies_to_service"),
                {
                    "src_id": ent_name,
                    "tgt_id": svc_name,
                    "description": "Узел применяется к услуге",
                    "keywords": "applies_to_service",
                    "weight": 1.0,
                    "source_id": source_id,
                    "file_path": file_path,
                },
            )

        for eid in _collect_ids(data.get("employee_ids")):
            emp_name = _employee_entity_name(eid)
            _iter_unique_add(
                entities,
                seen_entities,
                ("entity", emp_name),
                {
                    "entity_name": emp_name,
                    "entity_type": "employee",
                    "description": f"SQNS employee id={eid}",
                    "source_id": source_id,
                    "file_path": file_path,
                },
            )
            _iter_unique_add(
                relationships,
                seen_relations,
                ("rel", ent_name, emp_name, "handled_by_employee"),
                {
                    "src_id": ent_name,
                    "tgt_id": emp_name,
                    "description": "Узел про конкретного сотрудника",
                    "keywords": "handled_by_employee",
                    "weight": 1.0,
                    "source_id": source_id,
                    "file_path": file_path,
                },
            )

        # constraints.must_follow_node_refs → логические prerequisites
        constraints = data.get("constraints") if isinstance(data.get("constraints"), dict) else {}
        must_follow = _collect_ids(constraints.get("must_follow_node_refs"))
        for src_node_id in must_follow:
            src_node = nodes_by_id.get(src_node_id)
            if not src_node:
                continue
            src_data = src_node.get("data") if isinstance(src_node.get("data"), dict) else {}
            src_ref = (
                _str(src_data.get("title"))
                or _str(src_data.get("label"))
                or src_node_id
            )
            src_ent = _node_entity_name(flow_id, src_ref)
            _iter_unique_add(
                relationships,
                seen_relations,
                ("rel", src_ent, ent_name, "must_precede"),
                {
                    "src_id": src_ent,
                    "tgt_id": ent_name,
                    "description": "Обязательный логический порядок (must_precede)",
                    "keywords": "must_precede prerequisite",
                    "weight": 2.0,
                    "source_id": source_id,
                    "file_path": file_path,
                },
            )

    # ── Vue Flow edges → relationships (leads_to / branches_to) ──────────────
    for e in raw_edges:
        if not isinstance(e, dict):
            continue
        src_id = e.get("source")
        tgt_id = e.get("target")
        if not isinstance(src_id, str) or not isinstance(tgt_id, str):
            continue
        src_node = nodes_by_id.get(src_id)
        tgt_node = nodes_by_id.get(tgt_id)
        if not src_node or not tgt_node:
            continue

        src_data = src_node.get("data") if isinstance(src_node.get("data"), dict) else {}
        tgt_data = tgt_node.get("data") if isinstance(tgt_node.get("data"), dict) else {}
        src_ref = _str(src_data.get("title")) or _str(src_data.get("label")) or src_id
        tgt_ref = _str(tgt_data.get("title")) or _str(tgt_data.get("label")) or tgt_id
        src_ent = _node_entity_name(flow_id, src_ref)
        tgt_ent = _node_entity_name(flow_id, tgt_ref)

        src_type = _str(src_data.get("node_type"))
        label = _str(e.get("label"))
        is_branch = src_type == "condition"
        rel_kw = "branches_to" if is_branch else "leads_to"
        if not label and is_branch:
            handle = _str(e.get("sourceHandle"))
            if handle.startswith("branch:"):
                label = "ветка " + handle.replace("branch:", "").strip()[:12]
            elif handle:
                label = handle.replace("cond-", "ветка ")
        description = f"Ветка: {label}" if label else "Переход в потоке"
        _iter_unique_add(
            relationships,
            seen_relations,
            ("rel", src_ent, tgt_ent, rel_kw + ":" + label),
            {
                "src_id": src_ent,
                "tgt_id": tgt_ent,
                "description": description,
                "keywords": f"{rel_kw} {label}".strip(),
                "weight": 1.0,
                "source_id": source_id,
                "file_path": file_path,
            },
        )

    return {
        "entities": entities,
        "relationships": relationships,
        "chunks": chunks,
    }

