from __future__ import annotations

import os


def resolve_secret(secrets_ref: str | None) -> str | None:
    if not secrets_ref:
        return None
    return os.getenv(secrets_ref) or os.getenv(f"SECRET_{secrets_ref.upper()}")
