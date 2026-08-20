from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import app.services.function_rules_runtime as runtime
from app.services.function_rules_runtime import (
    _resolve_admin_notification_target,
    execute_post_actions,
)


class _FakeDb:
    """Минимальная замена AsyncSession: раннеру нужны только get() и add()."""

    def __init__(self, agent: object | None) -> None:
        self._agent = agent
        self.added: list[object] = []

    async def get(self, _model: object, _pk: object) -> object | None:
        return self._agent

    def add(self, obj: object) -> None:
        self.added.append(obj)


def _agent(*, enabled: bool = True, token: str | None = "agent-token", chat: str | None = "agent-chat"):
    return SimpleNamespace(
        name="Стилия",
        admin_notification_enabled=enabled,
        admin_notification_bot_token=token,
        admin_notification_chat_id=chat,
    )


def _action(action_type: str, config: dict | None = None):
    return SimpleNamespace(
        id=uuid4(),
        action_type=action_type,
        action_config=config or {},
        on_status="always",
        order_index=0,
        enabled=True,
    )


async def _run(db, actions, context=None):
    return await execute_post_actions(
        db,
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id="telegram:306597938",
        trace_id="trace-test",
        user=SimpleNamespace(user_id=uuid4()),
        actions=actions,
        execution_status="success",
        context=context or {},
    )


# --- разрешение реквизитов ------------------------------------------------


def test_resolve_target_prefers_explicit_config_over_agent_settings() -> None:
    db = _FakeDb(_agent(enabled=False))
    token, chat, name, skip = asyncio.run(
        _resolve_admin_notification_target(
            db, agent_id=uuid4(), cfg={"bot_token": "cfg-token", "chat_id": "cfg-chat"}
        )
    )
    # Явная пара работает даже при выключенном общем тумблере агента.
    assert (token, chat, skip) == ("cfg-token", "cfg-chat", None)
    assert name == "Стилия"


def test_resolve_target_falls_back_to_agent_settings() -> None:
    db = _FakeDb(_agent())
    token, chat, _name, skip = asyncio.run(
        _resolve_admin_notification_target(db, agent_id=uuid4(), cfg={})
    )
    assert (token, chat, skip) == ("agent-token", "agent-chat", None)


def test_resolve_target_respects_disabled_toggle() -> None:
    db = _FakeDb(_agent(enabled=False))
    _token, _chat, _name, skip = asyncio.run(
        _resolve_admin_notification_target(db, agent_id=uuid4(), cfg={})
    )
    assert skip == "admin_notifications_disabled"


def test_resolve_target_reports_missing_credentials() -> None:
    db = _FakeDb(_agent(token=None, chat=None))
    _token, _chat, _name, skip = asyncio.run(
        _resolve_admin_notification_target(db, agent_id=uuid4(), cfg={})
    )
    assert skip == "missing_bot_token_or_chat_id"


# --- notify_admin ---------------------------------------------------------


def test_notify_admin_renders_template_and_sends(monkeypatch) -> None:
    sent: dict = {}

    async def _fake_send(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(runtime, "send_admin_notification", _fake_send)

    db = _FakeDb(_agent())
    action = _action("notify_admin", {"message": "Клиент просит {{service}}"})
    results, _ctx = asyncio.run(_run(db, [action], {"service": "биоревитализацию"}))

    assert results[0].status == "success"
    assert sent["message"] == "Клиент просит биоревитализацию"
    assert sent["chat_id"] == "agent-chat"
    # bot_token не должен утекать в трейс действия.
    assert "bot_token" not in results[0].details


def test_notify_admin_skips_when_notifications_disabled(monkeypatch) -> None:
    async def _fail(**_kwargs):
        raise AssertionError("отправка не должна вызываться")

    monkeypatch.setattr(runtime, "send_admin_notification", _fail)

    db = _FakeDb(_agent(enabled=False))
    results, _ctx = asyncio.run(_run(db, [_action("notify_admin")]))

    assert results[0].status == "skipped"
    assert results[0].details["reason"] == "admin_notifications_disabled"


def test_notify_admin_can_omit_client_context(monkeypatch) -> None:
    sent: dict = {}

    async def _fake_send(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(runtime, "send_admin_notification", _fake_send)

    db = _FakeDb(_agent())
    action = _action("notify_admin", {"message": "тихо", "include_context": False})
    asyncio.run(_run(db, [action], {"last_user_message": "здравствуйте"}))

    assert sent["last_client_message"] is None


# --- handoff_to_operator --------------------------------------------------


def test_handoff_pauses_dialog_and_notifies(monkeypatch) -> None:
    paused: dict = {}
    alerted: dict = {}

    async def _fake_pause(_db, **kwargs):
        paused.update(kwargs)

    async def _fake_alert(**kwargs):
        alerted.update(kwargs)
        return True

    monkeypatch.setattr(runtime, "_pause_dialog_and_user", _fake_pause)
    monkeypatch.setattr(runtime, "send_manager_pause_alert", _fake_alert)

    db = _FakeDb(_agent())
    action = _action(
        "handoff_to_operator",
        {"client_message": "Передаю администратору", "reason": "возврат средств"},
    )
    results, ctx = asyncio.run(_run(db, [action]))

    assert results[0].status == "success"
    assert ctx["should_pause"] is True
    assert ctx["messages_to_send"] == ["Передаю администратору"]
    assert paused["session_id"] == "telegram:306597938"
    assert alerted["reason"] == "возврат средств"
    assert results[0].details["notify"] == "sent"


def test_handoff_can_skip_notification(monkeypatch) -> None:
    async def _fake_pause(_db, **_kwargs):
        return None

    async def _fail(**_kwargs):
        raise AssertionError("уведомление отключено — отправки быть не должно")

    monkeypatch.setattr(runtime, "_pause_dialog_and_user", _fake_pause)
    monkeypatch.setattr(runtime, "send_manager_pause_alert", _fail)

    db = _FakeDb(_agent())
    action = _action("handoff_to_operator", {"notify_admin": False})
    results, ctx = asyncio.run(_run(db, [action]))

    assert results[0].details["notify"] == "disabled"
    assert ctx["should_pause"] is True


def test_handoff_defaults_reason_when_not_set(monkeypatch) -> None:
    alerted: dict = {}

    async def _fake_pause(_db, **_kwargs):
        return None

    async def _fake_alert(**kwargs):
        alerted.update(kwargs)
        return True

    monkeypatch.setattr(runtime, "_pause_dialog_and_user", _fake_pause)
    monkeypatch.setattr(runtime, "send_manager_pause_alert", _fake_alert)

    db = _FakeDb(_agent())
    asyncio.run(_run(db, [_action("handoff_to_operator")]))

    assert alerted["reason"] == "передача оператору"
