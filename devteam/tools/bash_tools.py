from __future__ import annotations

import subprocess
from devteam.config import config


def bash_execute(command: str, timeout: int = 60, workdir: str | None = None) -> str:
    for denied in config.bash_deny_patterns:
        if denied in command:
            return f"[BLOCKED] forbidden pattern: {denied}"
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=workdir or config.project_root,
        )
        out = ((result.stdout or "") + (result.stderr or "")).strip()
        if len(out) > 4000:
            out = out[:2000] + "\n...[truncated]...\n" + out[-1000:]
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] exceeded {timeout}s"
    except Exception as e:
        return f"[ERROR] {e}"
