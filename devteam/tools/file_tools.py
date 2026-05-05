from __future__ import annotations

import subprocess
from pathlib import Path

from devteam.config import config

_ROOT = Path(config.project_root)


def _safe(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = _ROOT / p
    p = p.resolve()
    if not str(p).startswith(str(_ROOT)):
        raise PermissionError(f"Path outside project root: {p}")
    return p


def read_file(path: str) -> str:
    p = _safe(path)
    if not p.exists():
        return f"[ERROR] not found: {path}"
    if p.stat().st_size > 200_000:
        return f"[ERROR] file too large: {path}"
    return p.read_text(errors="replace")


def write_file(path: str, content: str) -> str:
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"[OK] written {len(content)} chars → {path}"


def list_directory(path: str = "", pattern: str = "*") -> str:
    p = _safe(path or ".")
    if not p.exists():
        return f"[ERROR] not found: {path}"
    items = sorted(p.glob(pattern))[:100]
    lines = [f"  {'/' if i.is_dir() else ' '} {i.relative_to(_ROOT)}" for i in items]
    return "\n".join(lines) or "(empty)"


def search_code(pattern: str, path: str = "", file_glob: str = "*.py") -> str:
    search_path = str(_safe(path or "."))
    result = subprocess.run(
        ["grep", "-rn", "--include", file_glob, "-m", "5", pattern, search_path],
        capture_output=True, text=True, timeout=15,
    )
    out = result.stdout.strip()
    return out[:3000] if out else f"[no matches for '{pattern}']"
