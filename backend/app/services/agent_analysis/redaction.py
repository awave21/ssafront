from __future__ import annotations

import re
from typing import Any

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\-\s()]{8,}\d)(?!\w)")
_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_TOKEN_RE = re.compile(r"\b(?:sk|pk|rk|xoxb|ghp|glpat|AIza)[\w\-]{8,}\b")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9._-]{10,}\.[A-Za-z0-9._-]{10,}\b")


def redact_text(value: str) -> str:
    text = value
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = _CARD_RE.sub("[REDACTED_CARD]", text)
    text = _TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    text = _JWT_RE.sub("[REDACTED_JWT]", text)
    return text


def redact_any(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_any(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lower_key = key.lower()
            if lower_key in {
                "password",
                "pass",
                "token",
                "api_key",
                "apikey",
                "secret",
                "authorization",
                "cookie",
                "set-cookie",
            }:
                redacted[key] = "[REDACTED_SECRET]"
            else:
                redacted[key] = redact_any(item)
        return redacted
    return value
