from __future__ import annotations

from types import SimpleNamespace

from app.services.runtime.tool_calls import extract_tools_called


class _ResultStub:
    def __init__(self, messages: list[SimpleNamespace]) -> None:
        self._messages = messages

    def all_messages(self) -> list[SimpleNamespace]:
        return self._messages


def _msg(parts: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(parts=parts)


def _tool_call_part(*, name: str, tool_call_id: str, args: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(part_kind="tool-call", tool_name=name, tool_call_id=tool_call_id, args=args)


def _tool_return_part(
    *,
    tool_call_id: str,
    tool_name: str | None = None,
    args: dict[str, object] | None = None,
    reaction: list[str] | None = None,
) -> SimpleNamespace:
    payload: dict[str, object] = {}
    if tool_name is not None:
        payload["tool_name"] = tool_name
    if args is not None:
        payload["args"] = args
    if reaction is not None:
        payload["__post_tool_reaction_messages"] = reaction
    return SimpleNamespace(part_kind="tool-return", tool_call_id=tool_call_id, content=payload)


def test_extract_tools_called_ignores_historical_tool_calls() -> None:
    current_call = _tool_call_part(name="current_tool", tool_call_id="call-1", args={"q": "now"})
    history_call = _tool_call_part(name="history_tool", tool_call_id="call-old", args={"q": "old"})

    new_messages = [_msg([current_call])]
    result = _ResultStub(messages=[_msg([history_call]), _msg([current_call])])

    tools_called = extract_tools_called(result=result, new_messages=new_messages, trace_id="trace-1")

    assert len(tools_called) == 1
    assert tools_called[0]["name"] == "current_tool"
    assert tools_called[0]["tool_call_id"] == "call-1"
    assert tools_called[0]["source"] == "new_messages"


def test_extract_tools_called_enriches_current_call_from_all_messages_by_tool_call_id() -> None:
    call = _tool_call_part(name="admin_call", tool_call_id="call-2", args={"name": "LLM"})
    tool_return = _tool_return_part(
        tool_call_id="call-2",
        tool_name="admin_call",
        args={"name": "Merged"},
        reaction=["Соединяю с оператором"],
    )

    # Simulate a provider/result shape where tool return is discoverable in all_messages.
    new_messages = [_msg([call])]
    result = _ResultStub(messages=[_msg([call]), _msg([tool_return])])

    tools_called = extract_tools_called(result=result, new_messages=new_messages, trace_id="trace-2")

    assert len(tools_called) == 1
    assert tools_called[0]["name"] == "admin_call"
    assert tools_called[0]["tool_call_id"] == "call-2"
    assert tools_called[0]["llm_args"] == {"name": "LLM"}
    assert tools_called[0]["execution_args"] == {"name": "Merged"}
    assert tools_called[0]["post_tool_reaction_messages"] == ["Соединяю с оператором"]
    assert tools_called[0]["result"] == {
        "tool_name": "admin_call",
        "args": {"name": "Merged"},
        "__post_tool_reaction_messages": ["Соединяю с оператором"],
    }
