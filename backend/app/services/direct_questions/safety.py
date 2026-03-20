from __future__ import annotations

import re


_SYSTEM_BLOCK_RE = re.compile(r"<system>(.*?)</system>", flags=re.IGNORECASE | re.DOTALL)


def sanitize_direct_question_content(content: str) -> str:
    """
    Guardrail against prompt/tool injection from managed content.
    """
    lowered = content.lower()
    blocked_fragments = (
        "ignore previous instructions",
        "ignore all previous instructions",
        "disable tools",
        "do not use tools",
        "override system",
        "system prompt",
    )
    if any(fragment in lowered for fragment in blocked_fragments):
        return "[Direct question content sanitized for safety]"
    return content


def split_direct_question_content(content: str) -> tuple[str | None, str]:
    """
    Extract optional <system>...</system> instructions and user-visible content.

    Returns:
        (system_instruction, user_content)
    """
    if not content:
        return None, ""

    instructions: list[str] = []
    for match in _SYSTEM_BLOCK_RE.finditer(content):
        block = (match.group(1) or "").strip()
        if block:
            instructions.append(block)

    user_content = _SYSTEM_BLOCK_RE.sub("", content).strip()
    system_instruction = "\n\n".join(instructions).strip() if instructions else None

    # Fallback to original content when only tags/noise were provided.
    if not user_content:
        user_content = content.strip()

    return system_instruction, user_content
