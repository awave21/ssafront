from __future__ import annotations

from app.services.run_service import _extract_forced_reaction_output


def test_extract_forced_reaction_output_returns_none_without_messages() -> None:
    assert _extract_forced_reaction_output([]) is None
    assert _extract_forced_reaction_output([{"name": "tool"}]) is None


def test_extract_forced_reaction_output_collects_messages_in_order() -> None:
    tools_called = [
        {"name": "a", "source": "new_messages", "post_tool_reaction_messages": ["Первое", "  ", "Второе"]},
        {"name": "b", "source": "new_messages", "post_tool_reaction_messages": ["Третье"]},
    ]

    output = _extract_forced_reaction_output(tools_called)

    assert output == "Первое\nВторое\nТретье"


def test_extract_forced_reaction_output_ignores_non_current_run_calls() -> None:
    tools_called = [
        {"name": "history_tool", "post_tool_reaction_messages": ["Старое"]},
        {"name": "new_tool", "source": "new_messages", "post_tool_reaction_messages": ["Новое"]},
    ]

    output = _extract_forced_reaction_output(tools_called)

    assert output == "Новое"
