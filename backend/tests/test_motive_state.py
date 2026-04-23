"""Тесты на чистые функции motive_state и script_flow_tool.

Не требуют БД/retriever backend — проверяют логику `render_state_snapshot`,
`_rerank_matches`, `_split_constraints_hard_soft`, `_merge_unique` и
`is_state_empty`.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4


def _mk_state(**overrides):
    from app.services.runtime.motive_state import MotiveState

    base = dict(
        session_id=UUID(int=1),
        agent_id=UUID(int=2),
        tenant_id=UUID(int=3),
        detected_motive_ids=[],
        raised_objection_ids=[],
        closed_objection_ids=[],
        asked_followup_questions=[],
        shown_proof_ids=[],
        blocked_tactic_ids=[],
        emotional_state=None,
        funnel_stage=None,
        emotional_pause_used=False,
        last_diagnosis=None,
        detected_service_id=None,
        detected_employee_id=None,
    )
    base.update(overrides)
    return MotiveState(**base)


def test_is_state_empty():
    from app.services.runtime.motive_state import MotiveState, is_state_empty

    empty = MotiveState.empty(session_id=UUID(int=1), agent_id=UUID(int=2), tenant_id=UUID(int=3))
    assert is_state_empty(empty)

    loaded = _mk_state(detected_motive_ids=["m1"])
    assert not is_state_empty(loaded)


def test_render_state_snapshot_open_vs_closed_objections():
    from app.services.runtime.motive_state import render_state_snapshot

    state = _mk_state(
        detected_motive_ids=["m1", "m2"],
        raised_objection_ids=["o1", "o2", "o3"],
        closed_objection_ids=["o2"],
        asked_followup_questions=["Когда планируете начать?"],
        emotional_state="skeptical",
        funnel_stage="objection",
    )
    names = {"m1": "страх боли", "m2": "экономия", "o1": "дорого", "o2": "подумаю", "o3": "не уверен"}
    out = render_state_snapshot(state, entity_names=names)

    assert "страх боли" in out
    assert "Стадия воронки: objection" in out
    assert "Эмоциональное состояние клиента: skeptical" in out
    # o2 закрыт → не должно быть в списке открытых
    assert "дорого" in out  # o1 открыт
    assert "не уверен" in out  # o3 открыт
    # Заданный вопрос должен быть процитирован
    assert "Когда планируете начать?" in out


def test_merge_unique_preserves_order_dedupes():
    from app.services.runtime.motive_state import _merge_unique

    out = _merge_unique(["a", "b"], ["b", "c", "a", "d"])
    assert out == ["a", "b", "c", "d"]


def test_rerank_debuff_blocked_and_already_asked_and_boost_open_objections():
    from app.services.runtime.script_flow_tool import _rerank_matches

    # Мок entity_index с объекцией "дорого" и proof-ом "кейс доктора"
    obj_ent = SimpleNamespace(id=uuid4(), name="дорого", meta={})
    proof_ent = SimpleNamespace(id=uuid4(), name="кейс доктора Ивановой", meta={})
    entity_index = {
        "by_id": {},
        "by_type_and_name": {
            "objection": {"дорого": obj_ent},
            "proof": {"кейс доктора ивановой": proof_ent},
        },
    }

    state = _mk_state(
        raised_objection_ids=[str(obj_ent.id)],
        closed_objection_ids=[],
        blocked_tactic_ids=["flow_1#node_blocked"],
        asked_followup_questions=["Когда планируете начать?"],
    )

    matches = [
        {
            # Топ по retrieval ranking, но заблокирована (score * 0.3)
            "tactic_title": "Blocked one",
            "tactic_node_ref": "flow_1#node_blocked",
            "objection_names": [],
            "proof_names": [],
            "required_followup_question": None,
            "score": 1.0,
        },
        {
            # Закрывает open objection → буст * 1.5
            "tactic_title": "Closes дорого",
            "tactic_node_ref": "flow_1#node_good",
            "objection_names": ["дорого"],
            "proof_names": [],
            "required_followup_question": "А что для вас важнее — срок или цена?",
            "score": 0.6,
        },
        {
            # Её follow-up уже задавали → score * 0.5
            "tactic_title": "Repeats question",
            "tactic_node_ref": "flow_1#node_repeat",
            "objection_names": [],
            "proof_names": [],
            "required_followup_question": "Когда планируете начать?",
            "score": 0.9,
        },
    ]

    out = _rerank_matches(matches, state, entity_index, score_threshold=0.0, max_return=3)
    titles = [m["tactic_title"] for m in out]

    # "Closes дорого" должен оказаться выше "Blocked one" (0.3) и "Repeats question" (0.45)
    assert titles[0] == "Closes дорого"
    # Blocked tactic должен быть где-то в конце
    assert titles[-1] == "Blocked one"


def test_split_constraints_hard_soft():
    from app.services.runtime.script_flow_tool import _split_constraints_hard_soft

    hard_ent = SimpleNamespace(id=uuid4(), name="не обещать результат", meta={"is_hard": True})
    soft_ent = SimpleNamespace(id=uuid4(), name="избегать сленга", meta={"is_hard": False})
    unknown_soft = SimpleNamespace  # не попадёт в индекс

    entity_index = {
        "by_id": {},
        "by_type_and_name": {
            "constraint": {
                "не обещать результат": hard_ent,
                "избегать сленга": soft_ent,
            },
        },
    }

    hard, soft = _split_constraints_hard_soft(
        ["не обещать результат", "избегать сленга", "неизвестно"], entity_index
    )
    assert "не обещать результат" in hard
    assert "избегать сленга" in soft
    assert "неизвестно" in soft  # неизвестное по-умолчанию soft


def test_enrich_match_shape():
    from app.services.runtime.script_flow_tool import _enrich_match

    entity_index = {
        "by_id": {},
        "by_type_and_name": {
            "constraint": {
                "не обещать результат": SimpleNamespace(
                    id=uuid4(), name="не обещать результат", meta={"is_hard": True}
                ),
            },
        },
    }

    match = {
        "tactic_title": "T",
        "motive_names": ["страх боли"],
        "constraint_names": ["не обещать результат", "неизвестное"],
        "required_followup_question": "Когда?",
        "communication_style": "спокойный, конкретный",
        "preferred_phrases": ["разберём по порядку"],
        "score": 0.7,
    }
    out = _enrich_match(match, entity_index)
    assert out["communication_style"] == "спокойный, конкретный"
    assert out["style_hint"] is None
    assert "разберём по порядку" in out["preferred_phrases"]
    assert out["hard_constraints"] == ["не обещать результат"]
    assert out["soft_constraints"] == ["неизвестное"]


if __name__ == "__main__":  # удобно запускать напрямую
    import sys

    tests = [
        test_is_state_empty,
        test_render_state_snapshot_open_vs_closed_objections,
        test_merge_unique_preserves_order_dedupes,
        test_rerank_debuff_blocked_and_already_asked_and_boost_open_objections,
        test_split_constraints_hard_soft,
        test_enrich_match_shape,
    ]
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
        except Exception as e:  # noqa
            print(f"FAIL {t.__name__}: {e}")
            sys.exit(1)
    print("\nAll motive-state tests passed.")
