from __future__ import annotations

from types import SimpleNamespace

from app.services.function_rules_runtime import evaluate_condition, merge_scenario_rule_contexts


def test_merge_scenario_rule_contexts_messages_and_silent() -> None:
    a: dict = {"messages_to_send": ["x"]}
    b: dict = {"messages_to_send": ["y"], "silent_reaction": True}
    m = merge_scenario_rule_contexts(a, b)
    assert m["messages_to_send"] == ["x", "y"]
    assert m["silent_reaction"] is True


def test_scenario_reply_first_non_empty_message() -> None:
    """Как в apply_dialog_scenario_phases_before_llm: пустые элементы в messages_to_send пропускаются."""
    msgs = ["", "  ", "Здравствуйте"]
    first_reply = ""
    for item in msgs:
        text = str(item).strip()
        if text:
            first_reply = text
            break
    assert first_reply == "Здравствуйте"

    only_blanks = ["", " \n "]
    first_reply = ""
    for item in only_blanks:
        text = str(item).strip()
        if text:
            first_reply = text
            break
    assert first_reply == ""


def test_client_return_gap_matches() -> None:
    rule = SimpleNamespace(
        condition_type="client_return_gap",
        condition_config={"min_days": 1.0},
        allow_semantic=True,
    )
    r = evaluate_condition(
        rule,
        message="hi",
        context={"days_since_last_user_message": 2.5},
    )
    assert r.matched is True


def test_client_return_gap_no_prior() -> None:
    rule = SimpleNamespace(
        condition_type="client_return_gap",
        condition_config={"min_days": 1.0},
        allow_semantic=True,
    )
    r = evaluate_condition(rule, message="hi", context={"days_since_last_user_message": None})
    assert r.matched is False


def test_dialog_source_matches_platform() -> None:
    rule = SimpleNamespace(
        condition_type="dialog_source",
        condition_config={"platforms": ["telegram"]},
        allow_semantic=True,
    )
    r = evaluate_condition(
        rule,
        message="",
        context={"user_info": {"platform": "telegram"}},
    )
    assert r.matched is True


def test_start_param_equals() -> None:
    rule = SimpleNamespace(
        condition_type="start_param",
        condition_config={"equals": "promo"},
        allow_semantic=True,
    )
    r = evaluate_condition(
        rule,
        message="",
        context={"user_info": {"start_param": "promo"}},
    )
    assert r.matched is True
