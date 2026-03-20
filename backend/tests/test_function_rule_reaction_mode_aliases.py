from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.function_rule import FunctionRuleCreate, FunctionRuleUpdate


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("Отправить сообщение", "send_message"),
        ("Инструкция для AI", "ai_instruction"),
        ("Позволить AI ответить самому", "ai_self_reply"),
        ("Промолчать", "silent"),
    ],
)
def test_function_rule_create_normalizes_reaction_mode_aliases(raw_value: str, expected: str) -> None:
    payload = FunctionRuleCreate(name="rule", reaction_to_execution=raw_value)
    assert payload.reaction_to_execution == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("Отправить сообщение", "send_message"),
        ("Инструкция для AI", "ai_instruction"),
        ("Позволить AI ответить самому", "ai_self_reply"),
        ("Промолчать", "silent"),
    ],
)
def test_function_rule_update_normalizes_reaction_mode_aliases(raw_value: str, expected: str) -> None:
    payload = FunctionRuleUpdate(reaction_to_execution=raw_value)
    assert payload.reaction_to_execution == expected


def test_function_rule_create_rejects_unknown_reaction_mode() -> None:
    with pytest.raises(ValidationError):
        FunctionRuleCreate(name="rule", reaction_to_execution="неизвестно")
