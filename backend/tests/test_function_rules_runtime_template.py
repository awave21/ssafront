from __future__ import annotations

from app.services.function_rules_runtime import _extract_latest_tool_call_args, _render_template


def test_render_template_resolves_from_tool_result_context() -> None:
    context = {
        "tool_result": {
            "username": "Максимус",
            "product_name": "Premium",
            "nested": {"city": "Moscow"},
        }
    }
    payload = {
        "name": "{{username}}",
        "firstname_ff": "{{tool_result.username}}",
        "product_name_ff": "{{tool_result.product_name}}",
        "city": "{{tool_result.nested.city}}",
    }

    rendered = _render_template(payload, context)

    assert rendered["name"] == "Максимус"
    assert rendered["firstname_ff"] == "Максимус"
    assert rendered["product_name_ff"] == "Premium"
    assert rendered["city"] == "Moscow"


def test_render_template_clears_unknown_placeholders() -> None:
    rendered = _render_template({"name": "{{unknown_key}}", "text": "User: {{unknown_key}}"}, {})

    assert rendered["name"] == ""
    assert rendered["text"] == "User: "


def test_render_template_keeps_original_type_for_single_placeholder() -> None:
    rendered = _render_template("{{tool_result.score}}", {"tool_result": {"score": 42}})
    assert rendered == 42


def test_render_template_resolves_from_last_tool_result_args_fallback() -> None:
    context = {
        "last_tool_result": {
            "mode": "internal",
            "tool_name": "demo",
            "args": {"username": "Максимус", "product_name": "Premium"},
            "status": "ok",
        }
    }
    payload = {
        "firstname_ff": "{{username}}",
        "product_name_ff": "{{product_name}}",
    }

    rendered = _render_template(payload, context)

    assert rendered["firstname_ff"] == "Максимус"
    assert rendered["product_name_ff"] == "Premium"


def test_render_template_resolves_dynamic_key_from_deep_nested_result() -> None:
    context = {
        "last_tool_result": {
            "meta": {"request_id": "abc"},
            "payload": {"customer": {"first_name": "Ирина"}},
        }
    }

    rendered = _render_template({"firstname_ff": "{{first_name}}"}, context)
    assert rendered["firstname_ff"] == "Ирина"


def test_render_template_resolves_from_tool_call_args_context() -> None:
    rendered = _render_template(
        {"firstname_ff": "{{username}}", "product_name_ff": "{{product_name}}"},
        {"tool_call_args": {"username": "Максим", "product_name": "Мишка"}},
    )
    assert rendered["firstname_ff"] == "Максим"
    assert rendered["product_name_ff"] == "Мишка"


def test_extract_latest_tool_call_args_prefers_matching_tool_name() -> None:
    context = {
        "tool_calls": [
            {"name": "other", "args": {"username": "Не тот"}},
            {"name": "order", "args": {"username": "Максим", "product_name": "Тедди"}},
        ]
    }
    extracted = _extract_latest_tool_call_args(context, preferred_tool_name="order")
    assert extracted == {"username": "Максим", "product_name": "Тедди"}
