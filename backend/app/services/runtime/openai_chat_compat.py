"""OpenAI Chat Completions: token limit parameter differs by model family."""

from __future__ import annotations

from typing import Any


def _unsupported_parameter_message(exc: BaseException, param: str) -> bool:
    text = str(exc).lower()
    needle = param.lower().strip("'\"")
    return "unsupported" in text and needle in text and "parameter" in text


async def chat_completions_create_with_max_out(
    client: Any,
    *,
    max_out_tokens: int,
    **kwargs: Any,
) -> Any:
    """
    Prefer ``max_completion_tokens`` (required for newer OpenAI models); fall back to
    ``max_tokens`` when the API rejects ``max_completion_tokens``.
    """
    try:
        return await client.chat.completions.create(
            **kwargs,
            max_completion_tokens=max_out_tokens,
        )
    except Exception as exc:
        if _unsupported_parameter_message(exc, "max_completion_tokens"):
            return await client.chat.completions.create(
                **kwargs,
                max_tokens=max_out_tokens,
            )
        raise
