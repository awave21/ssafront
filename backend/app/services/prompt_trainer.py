"""Мета-агент для генерации улучшенного system prompt на основе пользовательских коррекций."""
from __future__ import annotations

import structlog
from pydantic import BaseModel

from app.db.models.prompt_training_feedback import PromptTrainingFeedback

logger = structlog.get_logger(__name__)

META_SYSTEM_PROMPT = """\
Ты эксперт по проектированию system prompt для production-ассистентов.

ЦЕЛЬ
Переписать текущий system prompt с учетом всего пользовательского фидбека, сохранив исходный смысл,
повысив надежность и качество поведения агента.

ПРИНЦИПЫ PROMPT ENGINEERING
- Разделяй внутреннюю управляющую логику и пользовательский стиль общения.
- Явно задавай приоритеты правил на случай конфликтов.
- Пиши кратко, однозначно и применимо на практике.
- Удаляй дублирование и устраняй противоречия.
- Предпочитай позитивные, конструктивные инструкции.
- Используй строгую структуру, если важна предсказуемость результата.

ТРЕБОВАНИЯ К РЕКОНСТРУКЦИИ
Итоговый system prompt должен включать практичную архитектуру:
- ROLE и OBJECTIVE
- SCOPE и границы
- PRIORITY LOGIC (что важнее при конфликте правил)
- BEHAVIOR RULES (как действует ассистент)
- TOOL USAGE POLICY (если инструменты релевантны)
- FALLBACKS при неоднозначности, нехватке данных и неопределенности
- COMMUNICATION POLICY с естественной адаптацией под пользователя
- Эта структура — обязательный минимум, не максимум.
- Добавляй дополнительные разделы, если это повышает надежность, безопасность или качество.

ШАБЛОННЫЕ КАТЕГОРИИ (ИСПОЛЬЗУЙ КАК ОРИЕНТИР)
- Роль: консультант, менеджер, помощник, тьютор, креативщик, ассистент, бот-рецепционист
- Цель: консультировать, продавать, бронировать, создавать тексты, поддерживать, учить
- Стиль общения: дружелюбный, экспертный, неформальный, деловой, чуткий
- Особенности общения: использовать Emoji, отвечать кратко, быть ясным, писать как человек
- Логика поведения: описывать, какие функции и когда вызываются
- Функции: save_order_details, save_appointment, generate_text, submit_booking

СТРУКТУРА MARKDOWN (ОБЯЗАТЕЛЬНО)
- Поле `system_prompt` должно быть валидным Markdown.
- Должны быть разделы H2 в указанном порядке (допускаются русские эквиваленты):
  1) ## Role and Objective
  2) ## Scope and Boundaries
  3) ## Priority Logic
  4) ## Behavior Rules
  5) ## Tool Usage Policy
  6) ## Fallbacks and Uncertainty Handling
  7) ## Communication Policy
- Нельзя пропускать, переставлять или объединять эти разделы.
- Если данных не хватает, явно фиксируй допущения в нужном разделе.
- Не выводи неструктурированный текст вне разделов.

ПОЛИТИКА OUT-OF-SCOPE (ОБЯЗАТЕЛЬНО)
- Явно опиши, какие запросы вне зоны ответственности ассистента.
- Для таких запросов укажи вежливый отказ и перевод к поддерживаемым сценариям.

КРИТИЧЕСКОЕ ЯЗЫКОВОЕ ПРАВИЛО
- ВСЕГДА пиши на русском языке.
- Все поля structured output должны быть на русском языке.
- Не переходи на английский, даже если входные данные частично на английском.

OUTPUT CONTRACT (СТРОГО)
Верни structured output с полями:
1) reasoning: краткая техническая аргументация в 4-8 пунктах.
2) change_summary: одно понятное предложение, что изменено.
3) system_prompt: итоговый deploy-ready текст промпта без markdown fences и без комментариев.

КРИТЕРИИ КАЧЕСТВА
- Учитывается каждый элемент фидбека.
- Язык результата — русский.
- Итог согласованный, технически корректный и готовый к продакшену.
- Все обязательные разделы Markdown присутствуют и идут в правильном порядке.
"""

FEEDBACK_TYPE_LABELS = {
    "correction": "КОРРЕКЦИЯ (пользователь хочет изменить поведение)",
    "positive": "ПОЗИТИВ (поведение понравилось, это нужно сохранить)",
    "negative": "НЕГАТИВ (поведение не понравилось, нужно исправить)",
    "instruction": "ИНСТРУКЦИЯ (прямое правило от пользователя)",
}


class PromptGenerationResult(BaseModel):
    system_prompt: str
    reasoning: str
    change_summary: str


class ToolInfo(BaseModel):
    """Краткое описание инструмента агента для передачи мета-агенту."""

    name: str
    description: str
    parameters: dict | None = None


REQUIRED_MARKDOWN_SECTIONS = [
    "## Role and Objective",
    "## Scope and Boundaries",
    "## Priority Logic",
    "## Behavior Rules",
    "## Tool Usage Policy",
    "## Fallbacks and Uncertainty Handling",
    "## Communication Policy",
]

SECTION_HEADING_ALIASES: list[list[str]] = [
    ["role and objective", "роль и цель"],
    ["scope and boundaries", "область и границы"],
    ["priority logic", "логика приоритетов"],
    ["behavior rules", "правила поведения"],
    ["tool usage policy", "политика использования инструментов"],
    [
        "fallbacks and uncertainty handling",
        "обработка неопределенности и резервные стратегии",
        "fallbacks и обработка неопределенности",
    ],
    ["communication policy", "политика коммуникации", "коммуникационная политика"],
]


def _normalize_heading(heading: str) -> str:
    """Normalize markdown heading text for semantic section matching."""
    text = heading.strip()
    if text.startswith("## "):
        text = text[3:]
    text = text.lower()
    return " ".join(text.split())


def _heading_matches_aliases(heading: str, aliases: list[str]) -> bool:
    normalized = _normalize_heading(heading)
    return any(alias in normalized for alias in aliases)


def _validate_generated_prompt_structure(system_prompt: str) -> None:
    """Validate that generated prompt contains required sections in order.

    Supports localized section titles as long as semantic meaning and order are preserved.
    """
    headings = [
        line.strip()
        for line in system_prompt.splitlines()
        if line.strip().startswith("## ")
    ]

    pos = 0
    for required, aliases in zip(REQUIRED_MARKDOWN_SECTIONS, SECTION_HEADING_ALIASES):
        idx = -1
        for i in range(pos, len(headings)):
            if _heading_matches_aliases(headings[i], aliases):
                idx = i
                break
        if idx == -1:
            raise ValueError(
                f"Generated prompt is missing required section: '{required}'",
            )
        pos = idx + 1


def _format_feedbacks(feedbacks: list[PromptTrainingFeedback]) -> str:
    lines: list[str] = []
    for i, fb in enumerate(feedbacks, 1):
        label = FEEDBACK_TYPE_LABELS.get(fb.feedback_type, fb.feedback_type.upper())
        line = f"{i}. [{label}] {fb.correction_text}"
        if fb.agent_response:
            preview = fb.agent_response[:300]
            line += f"\n   Agent responded: {preview}"
        lines.append(line)
    return "\n".join(lines)


def _format_tools(tools: list[ToolInfo]) -> str:
    lines: list[str] = []
    for t in tools:
        line = f"- {t.name}: {t.description}"
        if t.parameters:
            props = t.parameters.get("properties", {})
            if props:
                param_names = ", ".join(props.keys())
                line += f" (params: {param_names})"
        lines.append(line)
    return "\n".join(lines)


async def generate_improved_prompt(
    current_prompt: str,
    feedbacks: list[PromptTrainingFeedback],
    meta_model: str = "openai:gpt-4.1",
    tools: list[ToolInfo] | None = None,
    openai_api_key: str | None = None,
) -> PromptGenerationResult:
    """Вызвать мета-агент для генерации улучшенного system prompt.

    Использует pydantic-ai Agent с structured output (PromptGenerationResult).
    """
    try:
        from pydantic_ai import Agent as PydanticAgent
    except ImportError as exc:
        raise RuntimeError("pydantic-ai is required for prompt training") from exc

    from app.services.runtime.model_resolver import resolve_model

    if not isinstance(meta_model, str) or not meta_model.strip():
        raise ValueError("meta_model must be a non-empty string")

    model = resolve_model(meta_model.strip(), openai_api_key=openai_api_key)
    meta_agent = PydanticAgent(
        model,
        output_type=PromptGenerationResult,
        system_prompt=META_SYSTEM_PROMPT,
    )

    feedback_text = _format_feedbacks(feedbacks)

    parts = [
        f"Текущий system prompt:\n---\n{current_prompt or '(пусто)'}\n---",
    ]

    if tools:
        tools_text = _format_tools(tools)
        parts.append(
            f"Доступные инструменты/функции ({len(tools)}):\n---\n{tools_text}\n---"
        )

    parts.append(
        f"Пользовательский фидбек ({len(feedbacks)} шт.):\n---\n{feedback_text}\n---"
    )
    parts.append(
        "Сгенерируй улучшенный system prompt, учитывая весь фидбек. "
        "КРИТИЧЕСКИ ВАЖНО: пиши итог ТОЛЬКО на русском языке. "
        "Используй ориентиры по категориям (роль, цель, стиль общения, особенности общения, логика поведения, функции) при формировании разделов."
    )

    user_prompt = "\n\n".join(parts)

    logger.info(
        "prompt_trainer_generating",
        meta_model=meta_model,
        feedback_count=len(feedbacks),
        tools_count=len(tools) if tools else 0,
        current_prompt_length=len(current_prompt or ""),
    )

    result = await meta_agent.run(user_prompt)

    output = result.output if hasattr(result, "output") else result.data
    _validate_generated_prompt_structure(output.system_prompt)
    logger.info(
        "prompt_trainer_generated",
        meta_model=meta_model,
        generated_prompt_length=len(output.system_prompt),
        change_summary=output.change_summary[:100],
    )
    return output
