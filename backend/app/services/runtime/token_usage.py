from __future__ import annotations

from typing import Any

import structlog
from pydantic_ai.messages import ModelResponse

from app.services.runtime.utils import (
    _extract_input_token_breakdown,
    _extract_usage_detail_tokens,
    _extract_usage_values,
)

logger = structlog.get_logger("app.services.runtime")


def extract_token_usage(
    result: Any,
    new_messages: list[Any],
    trace_id: str,
    model_name: str | None,
) -> tuple[int | None, int | None, int | None, list[dict[str, Any]]]:
    prompt_tokens = None
    completion_tokens = None
    total_tokens = None
    token_usage_steps: list[dict[str, Any]] = []

    try:
        all_messages = result.all_messages() if hasattr(result, "all_messages") else new_messages
    except Exception:
        all_messages = new_messages

    step_index = 0
    for msg in all_messages:
        if not isinstance(msg, ModelResponse):
            continue
        usage = getattr(msg, "usage", None)
        if usage is None:
            continue
        try:
            step_prompt, step_completion, step_total = _extract_usage_values(usage)
            if step_prompt is None and step_completion is None and step_total is None:
                continue
            step_cached_tokens, step_non_cached_tokens = _extract_input_token_breakdown(usage, step_prompt)
            step_detail_tokens = _extract_usage_detail_tokens(usage)
            step_index += 1
            token_usage_steps.append(
                {
                    "step_index": step_index,
                    "model_name": model_name,
                    "prompt_tokens": step_prompt,
                    "completion_tokens": step_completion,
                    "total_tokens": step_total,
                    "input_cached_tokens": step_cached_tokens,
                    "input_non_cached_tokens": step_non_cached_tokens,
                    "cache_read_tokens": step_detail_tokens.get("cache_read_tokens"),
                    "cache_write_tokens": step_detail_tokens.get("cache_write_tokens"),
                    "reasoning_tokens": step_detail_tokens.get("reasoning_tokens"),
                    "audio_tokens": step_detail_tokens.get("audio_tokens"),
                    "input_audio_tokens": step_detail_tokens.get("input_audio_tokens"),
                    "output_audio_tokens": step_detail_tokens.get("output_audio_tokens"),
                    "cache_audio_read_tokens": step_detail_tokens.get("cache_audio_read_tokens"),
                    "accepted_prediction_tokens": step_detail_tokens.get("accepted_prediction_tokens"),
                    "rejected_prediction_tokens": step_detail_tokens.get("rejected_prediction_tokens"),
                }
            )
        except Exception as exc:
            logger.warning(
                "token_usage_extraction_error",
                trace_id=trace_id,
                error=str(exc),
                usage_type=type(usage).__name__,
            )

    def _sum_steps(key: str) -> int | None:
        values = [step.get(key) for step in token_usage_steps if step.get(key) is not None]
        return sum(values) if values else None

    if token_usage_steps:
        prompt_tokens = _sum_steps("prompt_tokens")
        completion_tokens = _sum_steps("completion_tokens")
        total_tokens = _sum_steps("total_tokens")
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens
        logger.info(
            "token_usage_steps_extracted",
            trace_id=trace_id,
            steps_count=len(token_usage_steps),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        return prompt_tokens, completion_tokens, total_tokens, token_usage_steps

    try:
        result_usage = getattr(result, "usage", None)
        if result_usage is not None:
            prompt_tokens, completion_tokens, total_tokens = _extract_usage_values(result_usage)
            if prompt_tokens is not None or completion_tokens is not None or total_tokens is not None:
                cached_tokens, non_cached_tokens = _extract_input_token_breakdown(result_usage, prompt_tokens)
                detail_tokens = _extract_usage_detail_tokens(result_usage)
                token_usage_steps = [
                    {
                        "step_index": 1,
                        "model_name": model_name,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                        "input_cached_tokens": cached_tokens,
                        "input_non_cached_tokens": non_cached_tokens,
                        "cache_read_tokens": detail_tokens.get("cache_read_tokens"),
                        "cache_write_tokens": detail_tokens.get("cache_write_tokens"),
                        "reasoning_tokens": detail_tokens.get("reasoning_tokens"),
                        "audio_tokens": detail_tokens.get("audio_tokens"),
                        "input_audio_tokens": detail_tokens.get("input_audio_tokens"),
                        "output_audio_tokens": detail_tokens.get("output_audio_tokens"),
                        "cache_audio_read_tokens": detail_tokens.get("cache_audio_read_tokens"),
                        "accepted_prediction_tokens": detail_tokens.get("accepted_prediction_tokens"),
                        "rejected_prediction_tokens": detail_tokens.get("rejected_prediction_tokens"),
                    }
                ]
                logger.info(
                    "token_usage_extracted_from_result",
                    trace_id=trace_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
    except Exception as exc:
        logger.debug("token_usage_check_result_error", trace_id=trace_id, error=str(exc))

    return prompt_tokens, completion_tokens, total_tokens, token_usage_steps
