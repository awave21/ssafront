from __future__ import annotations

from devteam.tools.bash_tools import bash_execute

_ROOT = "/opt/myapp"


def git_status() -> str:
    return bash_execute("git status --short", workdir=_ROOT)


def git_diff(path: str = "") -> str:
    cmd = f"git diff HEAD -- {path}" if path else "git diff HEAD"
    return bash_execute(cmd, workdir=_ROOT)


def git_log(n: int = 10) -> str:
    return bash_execute(f"git log --oneline -n {n}", workdir=_ROOT)


def git_commit(message: str) -> str:
    return bash_execute(f'git add -A && git commit -m "{message}"', workdir=_ROOT)
