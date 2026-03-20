from __future__ import annotations

_SENSITIVE_HEADER_FRAGMENTS = ("authorization", "cookie", "token", "secret", "api-key", "signature")


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    masked: dict[str, str] = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if any(fragment in lower_key for fragment in _SENSITIVE_HEADER_FRAGMENTS):
            masked[key] = "***"
        else:
            masked[key] = value
    return masked
