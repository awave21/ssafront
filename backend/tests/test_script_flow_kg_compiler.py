from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from app.services.script_flow_kg_compiler import compile_script_flow_to_custom_kg


def _fake_flow(flow_def: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        name="Возражение: дорого",
        flow_definition=flow_def,
        flow_metadata={},
    )


def _fake_entity(entity_id: UUID, entity_type: str, name: str, description: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        id=entity_id,
        entity_type=entity_type,
        name=name,
        description=description,
    )


def test_compile_custom_kg_minimal_flow() -> None:
    motive_id = uuid4()
    objection_id = uuid4()
    flow = _fake_flow(
        {
            "nodes": [
                {
                    "id": "n1",
                    "type": "trigger",
                    "data": {
                        "title": "Спросил цену",
                        "node_type": "trigger",
                        "situation": "Клиент спрашивает стоимость",
                    },
                },
                {
                    "id": "n2",
                    "type": "expertise",
                    "data": {
                        "title": "Ценность часа врача",
                        "node_type": "expertise",
                        "situation": "Реакция на «дорого»",
                        "approach": "Показать стоимость часа",
                        "good_question": "Когда хотите начать курс?",
                        "service_ids": ["svc-a"],
                        "employee_ids": ["emp-1"],
                        "kg_links": {
                            "motive_ids": [str(motive_id)],
                            "objection_ids": [str(objection_id)],
                        },
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2", "label": "далее"},
            ],
        }
    )

    library = [
        _fake_entity(motive_id, "motive", "Страх обесценивания", "клиент боится, что дорого"),
        _fake_entity(objection_id, "objection", "Дорого", "budget"),
    ]

    kg = compile_script_flow_to_custom_kg(flow=flow, library_entities=library)

    assert "entities" in kg and "relationships" in kg and "chunks" in kg

    ent_names = {e["entity_name"] for e in kg["entities"]}
    # flow-root
    assert any(n.startswith("flow:") for n in ent_names)
    # node entities
    assert any("#node:Ценность часа врача" in n for n in ent_names)
    # library
    assert f"kg:motive:{motive_id}" in ent_names
    assert f"kg:objection:{objection_id}" in ent_names
    # service/employee shadow entities
    assert "svc:svc-a" in ent_names
    assert "emp:emp-1" in ent_names

    rel_keywords = {r["keywords"] for r in kg["relationships"]}
    assert any("motivated_by" in k for k in rel_keywords)
    assert any("answers" in k for k in rel_keywords)
    assert any("applies_to_service" in k for k in rel_keywords)
    assert any("handled_by_employee" in k for k in rel_keywords)
    assert any("leads_to" in k for k in rel_keywords)

    # chunks
    assert any("Ценность часа врача" in c["content"] for c in kg["chunks"])
    # source_id is consistent across all produced records
    for bucket in ("entities", "relationships", "chunks"):
        for rec in kg[bucket]:
            assert rec["source_id"] == f"flow:{flow.id}"


def test_compile_custom_kg_branching_condition() -> None:
    flow = _fake_flow(
        {
            "nodes": [
                {
                    "id": "cond",
                    "type": "condition",
                    "data": {"title": "Первый раз?", "node_type": "condition"},
                },
                {
                    "id": "t1",
                    "type": "expertise",
                    "data": {"title": "Онбординг", "node_type": "expertise"},
                },
                {
                    "id": "t2",
                    "type": "expertise",
                    "data": {"title": "Лояльный", "node_type": "expertise"},
                },
            ],
            "edges": [
                {"id": "e1", "source": "cond", "target": "t1", "sourceHandle": "cond-0", "label": "да"},
                {"id": "e2", "source": "cond", "target": "t2", "sourceHandle": "cond-1", "label": "нет"},
            ],
        }
    )
    kg = compile_script_flow_to_custom_kg(flow=flow, library_entities=[])
    rel_keywords = [r["keywords"] for r in kg["relationships"]]
    assert any("branches_to" in k for k in rel_keywords)
