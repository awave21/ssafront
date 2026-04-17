from __future__ import annotations

from app.services.script_flow_compiler import compile_script_flow_to_text


def test_compile_script_flow_minimal() -> None:
    text = compile_script_flow_to_text(
        name="Price objection",
        flow_metadata={"when_relevant": "User doubts implant price"},
        flow_definition={
            "nodes": [
                {
                    "id": "a",
                    "type": "block",
                    "data": {"title": "Acknowledge", "content": "Validate concern."},
                },
                {
                    "id": "b",
                    "type": "block",
                    "data": {"title": "Explain value", "content": "Warranty and materials."},
                },
            ],
            "edges": [{"id": "e1", "source": "a", "target": "b", "label": "continues"}],
        },
    )
    assert "Price objection" in text
    assert "User doubts implant price" in text
    assert "Acknowledge" in text
    assert "Explain value" in text
    assert "continues" in text or "Transition" in text


def test_compile_expertise_axis_sections() -> None:
    text = compile_script_flow_to_text(
        name="Axes",
        flow_metadata={},
        flow_definition={
            "nodes": [
                {
                    "id": "n1",
                    "data": {
                        "node_type": "expertise",
                        "title": "Цена",
                        "situation": "дорого",
                        "why_it_works": "нет ценности",
                        "approach": "перевести на ценность",
                        "watch_out": "не скидка",
                        "good_question": "Уточнить задачу?",
                        "example_phrases": ["фраза 1", "фраза 2"],
                    },
                },
            ],
            "edges": [],
        },
    )
    assert "▸ **Возражение / ситуация клиента**" in text
    assert "▸ **Мотив (психология)**" in text
    assert "▸ **Аргументы и тактика**" in text
    assert "▸ **Вариативные формулировки (примеры)**" in text
    assert "▸ **Табу (не делай)**" in text
    assert "▸ **Уточняющий вопрос**" in text


def test_compile_question_axis_order() -> None:
    text = compile_script_flow_to_text(
        name="Q",
        flow_metadata={},
        flow_definition={
            "nodes": [
                {
                    "id": "q1",
                    "data": {
                        "node_type": "question",
                        "title": "Уточнение",
                        "good_question": "Когда удобно?",
                        "situation": "после цены",
                    },
                },
            ],
            "edges": [],
        },
    )
    assert "▸ **Ключевой вопрос клиенту**" in text
    pos_q = text.index("Когда удобно")
    pos_ctx = text.index("после цены")
    assert pos_q < pos_ctx


def test_compile_trigger_axis() -> None:
    text = compile_script_flow_to_text(
        name="Tr",
        flow_metadata={},
        flow_definition={
            "nodes": [
                {
                    "id": "t1",
                    "data": {
                        "node_type": "trigger",
                        "title": "Вход",
                        "situation": "клиент спрашивает про срок",
                        "why_it_works": "нужна квалификация",
                    },
                },
            ],
            "edges": [],
        },
    )
    assert "▸ **Сигнал / ситуация входа**" in text
    assert "▸ **Зачем запускать этот сценарий**" in text
