# SPDX-FileCopyrightText: 2025 OpenAI
# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

DEFAULT_RUN_ID = "initial-run"
SESSION_ID = "debug-session"


def _resolve_log_path() -> Path:
    candidate = Path(__file__).resolve()
    for _ in range(8):
        cursor_dir = candidate / ".cursor"
        if cursor_dir.exists():
            cursor_dir.mkdir(parents=True, exist_ok=True)
            return cursor_dir / "debug.log"
        candidate = candidate.parent
    fallback = Path("/tmp")
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / "debug.log"


DEBUG_LOG_PATH = _resolve_log_path()


def emit_debug_log(
    location: str,
    message: str,
    data: dict[str, Any],
    hypothesisId: str,
    *,
    runId: str | None = None,
) -> None:
    """Append a single NDJSON debug line for the current hypothesis."""
    payload = {
        "sessionId": SESSION_ID,
        "runId": runId or DEFAULT_RUN_ID,
        "hypothesisId": hypothesisId,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with DEBUG_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(payload) + "\n")
