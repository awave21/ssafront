"""Расход считается по сообщениям своего запуска, а не по всей истории.

Раньше здесь звался result.all_messages(), а он возвращает историю сессии
вместе с новыми сообщениями. Каждый ответ модели из истории нёс свой usage,
и он пересчитывался заново на каждом следующем запуске: расход рос квадратично
по длине диалога. На проде это давало 2,5-кратное завышение списаний.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("pydantic_ai")

from pydantic_ai.messages import ModelResponse, TextPart  # noqa: E402
from pydantic_ai.usage import RequestUsage  # noqa: E402

from app.services.runtime.token_usage import extract_token_usage  # noqa: E402


def _response(prompt: int, completion: int) -> ModelResponse:
    return ModelResponse(
        parts=[TextPart(content="ответ")],
        usage=RequestUsage(input_tokens=prompt, output_tokens=completion),
    )


class _Result:
    """Ответ PydanticAI: all_messages включает историю, new_messages — нет."""

    def __init__(self, history: list, fresh: list) -> None:
        self._all = [*history, *fresh]

    def all_messages(self) -> list:
        return self._all


def test_history_is_not_billed_again() -> None:
    history = [_response(4_000, 40), _response(5_000, 50)]
    fresh = [_response(6_000, 60)]

    prompt, completion, _total, steps = extract_token_usage(
        _Result(history, fresh), fresh, "trace", "openai:gpt-4.1-mini"
    )

    assert len(steps) == 1
    assert prompt == 6_000
    assert completion == 60


def test_several_calls_in_one_run_are_all_counted() -> None:
    fresh = [_response(3_000, 30), _response(4_000, 40)]

    prompt, completion, _total, steps = extract_token_usage(
        _Result([_response(9_000, 90)], fresh), fresh, "trace", "openai:gpt-4.1-mini"
    )

    assert len(steps) == 2
    assert prompt == 7_000
    assert completion == 70


def test_falls_back_to_all_messages_when_new_have_no_usage() -> None:
    # Перестать считать расход молча хуже, чем посчитать с запасом.
    history = [_response(5_000, 50)]

    _prompt, _completion, _total, steps = extract_token_usage(
        _Result(history, []), [], "trace", "openai:gpt-4.1-mini"
    )

    assert len(steps) == 1


def test_empty_everything_gives_no_steps() -> None:
    result = SimpleNamespace()

    prompt, completion, total, steps = extract_token_usage(result, [], "trace", "модель")

    assert steps == []
    assert (prompt, completion, total) == (None, None, None)
