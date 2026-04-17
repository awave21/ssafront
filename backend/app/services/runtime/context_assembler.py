from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_TOOL_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "knowledge": (
        "документ", "документы", "инструкция", "регламент", "файл", "файлы",
        "knowledge", "kb", "faq", "manual", "guide", "policy",
    ),
    "direct_questions": (
        "вопрос", "вопросы", "ответ", "ответы", "база знаний", "faq",
        "карточка", "карточки", "готовый ответ", "прямой ответ",
    ),
    "expertise": (
        # Явные возражения
        "возраж", "дорого", "дешевле", "сравн", "другой клиник", "конкурент",
        "скидк", "скидки", "цен", "стоимост",
        # Колебания и откладывание
        "подумаю", "подумать", "не уверен", "посмотрю", "позже", "потом",
        "не готов", "ещё не", "может быть", "если что", "пока не",
        "не знаю", "наверное", "возможно",
        # Недоверие / страхи
        "боюсь", "страшно", "не хочу", "сомнева", "побоку", "рискован",
        # Скрипты / экспертиза (технические)
        "скрипт", "скрипты", "objection", "expert", "expertise", "hesitat", "price",
    ),
    "directory": (
        "каталог", "справочник", "найди", "поиск", "услуга", "товар",
        "сотрудник", "мастер", "service", "directory", "catalog", "lookup",
    ),
}


@dataclass
class ScenarioPromptAssemblyResult:
    system_prompt_override: str | None
    kept_blocks: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


def normalize_augment_prompt_blocks(
    raw_blocks: Any,
    *,
    max_blocks: int,
    max_chars: int,
) -> tuple[list[str], dict[str, Any]]:
    if not isinstance(raw_blocks, list):
        return [], {
            "input_count": 0,
            "kept_count": 0,
            "kept_chars": 0,
            "dropped_empty": 0,
            "dropped_duplicates": 0,
            "dropped_overflow": 0,
            "truncated_last_block": False,
        }

    kept: list[str] = []
    seen: set[str] = set()
    kept_chars = 0
    dropped_empty = 0
    dropped_duplicates = 0
    dropped_overflow = 0
    truncated_last_block = False

    for raw in raw_blocks:
        text = str(raw).strip()
        if not text:
            dropped_empty += 1
            continue
        if text in seen:
            dropped_duplicates += 1
            continue
        if len(kept) >= max_blocks:
            dropped_overflow += 1
            continue

        remaining_chars = max_chars - kept_chars
        if remaining_chars <= 0:
            dropped_overflow += 1
            continue

        if len(text) > remaining_chars:
            text = text[:remaining_chars].rstrip()
            truncated_last_block = True

        if not text:
            dropped_overflow += 1
            continue

        kept.append(text)
        seen.add(text)
        kept_chars += len(text)

        if truncated_last_block:
            break

    return kept, {
        "input_count": len(raw_blocks),
        "kept_count": len(kept),
        "kept_chars": kept_chars,
        "dropped_empty": dropped_empty,
        "dropped_duplicates": dropped_duplicates,
        "dropped_overflow": dropped_overflow,
        "truncated_last_block": truncated_last_block,
    }


def select_optional_runtime_tool_categories(
    input_message: str,
    *,
    mode: str,
) -> tuple[set[str], dict[str, Any]]:
    normalized_mode = (mode or "eager").strip().lower()
    categories = set(_TOOL_CATEGORY_KEYWORDS.keys())
    if normalized_mode != "lazy_keywords":
        return categories, {"mode": normalized_mode or "eager", "matched_categories": sorted(categories)}

    message = (input_message or "").strip().lower()
    if not message:
        return categories, {
            "mode": normalized_mode,
            "matched_categories": sorted(categories),
            "reason": "empty_message",
        }

    matched: set[str] = set()
    for category, keywords in _TOOL_CATEGORY_KEYWORDS.items():
        if any(keyword in message for keyword in keywords):
            matched.add(category)

    # Keep a safe baseline when heuristics see no clear intent.
    # Include expertise so the get_expertise tool is always available — even for
    # ambiguous messages like "I need to think" or short replies.
    if not matched:
        matched = {"knowledge", "direct_questions", "expertise"}

    return matched, {
        "mode": normalized_mode,
        "matched_categories": sorted(matched),
    }


def build_system_prompt_override(
    base_system_prompt: str | None,
    merged_scenario_ctx: dict[str, Any],
    *,
    max_blocks: int,
    max_chars: int,
) -> ScenarioPromptAssemblyResult:
    aug_list = merged_scenario_ctx.get("augment_prompt")
    if not isinstance(aug_list, list) or not aug_list:
        return ScenarioPromptAssemblyResult(system_prompt_override=None)

    normalized_aug_list, aug_meta = normalize_augment_prompt_blocks(
        aug_list,
        max_blocks=max_blocks,
        max_chars=max_chars,
    )
    extra = "\n\n".join(normalized_aug_list)
    if not extra:
        return ScenarioPromptAssemblyResult(
            system_prompt_override=None,
            kept_blocks=normalized_aug_list,
            meta=aug_meta,
        )

    base_prompt = (base_system_prompt or "").strip()
    override = f"{base_prompt}\n\n{extra}".strip() if base_prompt else extra
    return ScenarioPromptAssemblyResult(
        system_prompt_override=override,
        kept_blocks=normalized_aug_list,
        meta=aug_meta,
    )
