from __future__ import annotations

import pytest

from app.services.prompt_trainer import _validate_generated_prompt_structure


def test_validate_generated_prompt_structure_accepts_english_sections() -> None:
    prompt = """\
## Role and Objective
text
## Scope and Boundaries
text
## Priority Logic
text
## Behavior Rules
text
## Tool Usage Policy
text
## Fallbacks and Uncertainty Handling
text
## Communication Policy
text
"""
    _validate_generated_prompt_structure(prompt)


def test_validate_generated_prompt_structure_accepts_russian_sections() -> None:
    prompt = """\
## Роль и цель
текст
## Область и границы
текст
## Логика приоритетов
текст
## Правила поведения
текст
## Политика использования инструментов
текст
## Fallbacks и обработка неопределенности
текст
## Коммуникационная политика
текст
"""
    _validate_generated_prompt_structure(prompt)


def test_validate_generated_prompt_structure_requires_order() -> None:
    prompt = """\
## Role and Objective
text
## Priority Logic
text
## Scope and Boundaries
text
## Behavior Rules
text
## Tool Usage Policy
text
## Fallbacks and Uncertainty Handling
text
## Communication Policy
text
"""
    with pytest.raises(ValueError):
        _validate_generated_prompt_structure(prompt)
