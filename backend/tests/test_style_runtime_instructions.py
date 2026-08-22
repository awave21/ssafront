"""Стиль-слой доезжает до модели штатным механизмом PydanticAI.

Раньше блок склеивался со строкой system_prompt в orchestrator — так его
затирали сценарные фазы, пересобиравшие промпт. Теперь он подаётся как
runtime instructions на вызове run(): фреймворк сам дописывает его после
статических инструкций и переоценивает на каждом запуске.
"""

import asyncio

from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

BASE = "Базовый промпт агента."
STYLE = "## ГОЛОС ЭКСПЕРТА\n— «фраза эксперта»"


def _run(instructions: str | None) -> str:
    captured: dict[str, str] = {}

    def capture(messages, info):
        captured["instructions"] = messages[0].instructions or ""
        return ModelResponse(parts=[TextPart(content="ok")])

    agent = Agent(FunctionModel(capture), instructions=BASE)
    asyncio.run(agent.run("привет", instructions=instructions))
    return captured["instructions"]


def test_style_block_reaches_model_after_base_prompt():
    got = _run(STYLE)
    assert BASE in got
    assert "ГОЛОС ЭКСПЕРТА" in got
    assert got.index(BASE) < got.index("ГОЛОС ЭКСПЕРТА")


def test_base_prompt_survives_without_style():
    got = _run(None)
    assert got.strip() == BASE
