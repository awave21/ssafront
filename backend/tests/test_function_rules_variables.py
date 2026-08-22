from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.services.function_rules_runtime import execute_post_actions


class _FakeDb:
    async def get(self, _model: object, _pk: object) -> object | None:
        return None

    def add(self, _obj: object) -> None:
        return None


def _action(config: dict):
    return SimpleNamespace(
        id=uuid4(),
        action_type="set_variable",
        action_config=config,
        on_status="always",
        order_index=0,
        enabled=True,
    )


def _run(actions, context=None):
    return asyncio.run(
        execute_post_actions(
            _FakeDb(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            session_id="telegram:306597938",
            trace_id="trace-test",
            user=SimpleNamespace(user_id=uuid4()),
            actions=actions,
            execution_status="success",
            context=context or {},
        )
    )


def test_set_writes_value_and_marks_dirty() -> None:
    results, ctx = _run([_action({"name": "city", "value": "Москва"})])

    assert results[0].status == "success"
    assert ctx["variables"] == {"city": "Москва"}
    # Без флага run_rules_for_phase не запишет переменные в базу.
    assert ctx["variables_dirty"] is True


def test_set_renders_template_from_context() -> None:
    _results, ctx = _run(
        [_action({"name": "service", "value": "{{tool_result}}"})],
        {"tool_result": "биоревитализация"},
    )
    assert ctx["variables"]["service"] == "биоревитализация"


def test_increment_starts_from_zero_and_stays_integer() -> None:
    _results, ctx = _run([_action({"name": "visits", "operation": "increment", "value": "1"})])
    # Счётчик с нуля должен дать 1, а не 1.0 — иначе в тексты подставится «1.0».
    assert ctx["variables"]["visits"] == 1
    assert isinstance(ctx["variables"]["visits"], int)


def test_increment_adds_to_existing_value() -> None:
    _results, ctx = _run(
        [_action({"name": "visits", "operation": "increment", "value": "2"})],
        {"variables": {"visits": 3}},
    )
    assert ctx["variables"]["visits"] == 5


def test_increment_falls_back_to_one_on_garbage_step() -> None:
    _results, ctx = _run(
        [_action({"name": "visits", "operation": "increment", "value": "не число"})],
        {"variables": {"visits": 1}},
    )
    assert ctx["variables"]["visits"] == 2


def test_clear_removes_variable() -> None:
    _results, ctx = _run(
        [_action({"name": "city", "operation": "clear"})],
        {"variables": {"city": "Москва", "visits": 2}},
    )
    assert ctx["variables"] == {"visits": 2}


def test_empty_name_is_skipped_without_touching_variables() -> None:
    results, ctx = _run([_action({"value": "что-то"})], {"variables": {"city": "Москва"}})

    assert results[0].status == "skipped"
    assert results[0].details["reason"] == "empty_name"
    assert ctx["variables"] == {"city": "Москва"}
    assert "variables_dirty" not in ctx


def test_later_action_sees_variable_set_by_earlier_one() -> None:
    _results, ctx = _run(
        [
            _action({"name": "city", "value": "Москва"}),
            _action({"name": "greeting", "value": "Привет, {{city}}"}),
        ]
    )
    # Второе действие читает переменную, записанную первым, в том же прогоне.
    assert ctx["variables"]["greeting"] == "Привет, Москва"
