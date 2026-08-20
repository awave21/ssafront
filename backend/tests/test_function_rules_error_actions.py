"""Действия «При ошибке» не выполнялись никогда.

execute_post_actions вызывался с жёстко зашитым execution_status="success",
поэтому фильтр отбрасывал все действия с on_status="error". Вариант в
интерфейсе был, эффекта не было.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.services.function_rules_runtime import (
    _classify_rule_tool_result,
    execute_post_actions,
)


class _FakeDb:
    def __init__(self) -> None:
        self.added: list[object] = []

    async def get(self, _model: object, _pk: object) -> object | None:
        return None

    def add(self, obj: object) -> None:
        self.added.append(obj)


def _action(on_status: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        action_type="set_variable",
        action_config={"name": "метка", "value": on_status},
        on_status=on_status,
        order_index=1,
        enabled=True,
    )


def _run(actions, status):
    return asyncio.run(
        execute_post_actions(
            _FakeDb(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            session_id="telegram:1",
            trace_id="trace",
            user=SimpleNamespace(user_id=uuid4()),
            actions=actions,
            execution_status=status,
            context={},
        )
    )


# --- распознавание ошибки вызова тула --------------------------------------


def test_webhook_error_field_makes_status_error() -> None:
    assert _classify_rule_tool_result({"error": "connection refused"}) == (
        "error",
        "connection refused",
    )


def test_http_status_above_400_is_error() -> None:
    status, reason = _classify_rule_tool_result({"error": None, "status_code": 502})

    assert status == "error"
    assert reason == "HTTP 502"


def test_successful_webhook_stays_success() -> None:
    assert _classify_rule_tool_result({"error": None, "status_code": 200}) == ("success", None)


def test_internal_tool_payload_stays_success() -> None:
    assert _classify_rule_tool_result({"mode": "internal", "status": "ok"}) == ("success", None)


def test_non_dict_payload_stays_success() -> None:
    assert _classify_rule_tool_result("готово") == ("success", None)


# --- фильтр по статусу -----------------------------------------------------


def test_error_action_runs_on_error() -> None:
    results, _ctx = _run([_action("error")], "error")

    assert [r.status for r in results] == ["success"]


def test_error_action_skipped_on_success() -> None:
    results, _ctx = _run([_action("error")], "success")

    assert results == []


def test_always_action_runs_in_both_cases() -> None:
    assert len(_run([_action("always")], "success")[0]) == 1
    assert len(_run([_action("always")], "error")[0]) == 1
