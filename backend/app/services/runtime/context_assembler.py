from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Группы optional data-тулов (knowledge, direct_questions, …): платформа всегда
# регистрирует их для модели; какие вызывать — решает LLM по описаниям тулов и промпту.
OPTIONAL_RUNTIME_TOOL_CATEGORY_IDS = frozenset(
    {"knowledge", "direct_questions", "expertise", "directory"}
)


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
    _input_message: str = "",
) -> tuple[set[str], dict[str, Any]]:
    """Expose all optional categories and let the LLM decide tool usage.

    This keeps runtime tool routing purely model-driven (system prompt +
    tool descriptions) without server-side message heuristics.
    """
    selected = {"knowledge", "direct_questions", "directory", "expertise"}
    return selected, {
        "matched_categories": sorted(selected),
        "selection": "llm_driven_optional_tools",
        "expertise_selected": True,
        "expertise_policy": "always_enabled_llm_decides",
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
