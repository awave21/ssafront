from __future__ import annotations

import re

_SENSITIVE_HEADER_FRAGMENTS = ("authorization", "cookie", "token", "secret", "api-key", "signature")


def sanitize_agent_reply_text(text: str) -> str:
    """Убрать технические параметры и repr-строки, заменить \\n на переносы строк."""
    if not text or not isinstance(text, str):
        return ""
    m = re.match(r"^AgentRunResult\(output=['\"](.+)['\"]\)\s*$", text.strip(), re.DOTALL)
    if m:
        text = m.group(1)
    elif text.strip().startswith("AgentRunResult("):
        inner = re.search(r"output=['\"](.+?)['\"]\)\s*$", text, re.DOTALL)
        if inner:
            text = inner.group(1)
    return text.replace("\\n", "\n").replace("\\t", "\t")


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    masked: dict[str, str] = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if any(fragment in lower_key for fragment in _SENSITIVE_HEADER_FRAGMENTS):
            masked[key] = "***"
        else:
            masked[key] = value
    return masked
