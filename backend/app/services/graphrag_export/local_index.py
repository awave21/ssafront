"""Локальный ``graphrag init`` / ``graphrag index`` в каталоге workspace агента."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import shutil
import sys
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.agent import Agent
from app.services.graphrag_export.graphrag_preview import agent_graphrag_workspace
from app.services.graphrag_export.sqns_corpus import gather_sqns_graphrag_sections, write_graphrag_sections_to_workspace
from app.services.tenant_llm_config import get_decrypted_api_key

logger = structlog.get_logger(__name__)

_PROMPT_TUNE_SKIP = frozenset({"", "off", "false", "none", "no"})


def _effective_prompt_tune_language(raw: str | None) -> str | None:
    s = (raw or "").strip()
    if not s or s.lower() in _PROMPT_TUNE_SKIP:
        return None
    return s


def _graphrag_argv_prefix(settings: Settings) -> list[str] | None:
    """
    Префикс argv для вызова CLI: ``graphrag …`` или ``python -m graphrag …``.
    """
    manual = (settings.microsoft_graphrag_cli or "").strip()
    if manual:
        return [manual]
    found = shutil.which("graphrag")
    if found:
        return [found]
    if importlib.util.find_spec("graphrag") is not None:
        return [sys.executable, "-m", "graphrag"]
    return None


async def _run_graphrag_subprocess(
    cwd: Path,
    args: list[str],
    env: dict[str, str],
    *,
    timeout_sec: float,
) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    out = (stdout or b"").decode("utf-8", errors="replace")
    err = (stderr or b"").decode("utf-8", errors="replace")
    return int(proc.returncode or 0), out, err


async def run_local_microsoft_graphrag_index(
    *,
    db: AsyncSession,
    agent: Agent,
    settings: Settings,
    active_sqns_only: bool = True,
) -> tuple[bool, str]:
    ws = agent_graphrag_workspace(settings, tenant_id=agent.tenant_id, agent=agent)
    if ws is None:
        return False, "Не задан MICROSOFT_GRAPHRAG_WORKSPACE_ROOT."

    ws.mkdir(parents=True, exist_ok=True)
    (ws / "input").mkdir(parents=True, exist_ok=True)
    (ws / "output").mkdir(parents=True, exist_ok=True)

    sections = await gather_sqns_graphrag_sections(db, agent.id, active_sqns_only=active_sqns_only)
    write_graphrag_sections_to_workspace(ws, sections)

    api_key = await get_decrypted_api_key(db, agent.tenant_id, "openai")
    if not api_key:
        return False, "Нет ключа OpenAI для организации (OPENAI_API_KEY)."

    prefix = _graphrag_argv_prefix(settings)
    if not prefix:
        return False, "Нет graphrag в PATH (pip install graphrag или MICROSOFT_GRAPHRAG_CLI)."

    env = {**os.environ, "OPENAI_API_KEY": api_key, "GRAPHRAG_API_KEY": api_key}

    timeout_sec = float(settings.microsoft_graphrag_subprocess_timeout_seconds)

    settings_yaml = ws / "settings.yaml"
    if not settings_yaml.is_file():
        init_args = [*prefix, "init", "--root", ".", "--force"]
        code, out, err = await _run_graphrag_subprocess(ws, init_args, env, timeout_sec=min(timeout_sec, 600))
        if code != 0:
            logger.warning("graphrag_init_failed", code=code, stderr=err[:2000])
            return False, f"graphrag init завершился с кодом {code}: {err or out}"[:2000]

    tune_lang = _effective_prompt_tune_language(settings.microsoft_graphrag_prompt_tune_language)
    if tune_lang:
        marker = ws / ".graphrag_prompt_language"
        prev = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
        if prev != tune_lang:
            tune_args = [
                *prefix,
                "prompt-tune",
                "--root",
                ".",
                "--language",
                tune_lang,
                "--limit",
                "15",
                "--selection-method",
                "random",
            ]
            tune_timeout = min(timeout_sec, 1200.0)
            try:
                code, out, err = await _run_graphrag_subprocess(ws, tune_args, env, timeout_sec=tune_timeout)
            except asyncio.TimeoutError:
                logger.warning("graphrag_prompt_tune_timeout", seconds=int(tune_timeout))
            else:
                if code != 0:
                    logger.warning(
                        "graphrag_prompt_tune_failed",
                        code=code,
                        stderr=err[:2000],
                        stdout=out[:500],
                    )
                else:
                    marker.write_text(tune_lang + "\n", encoding="utf-8")
                    logger.info("graphrag_prompt_tune_ok", language=tune_lang, workspace=str(ws))

    index_args = [*prefix, "index", "--root", "."]
    try:
        code, out, err = await _run_graphrag_subprocess(ws, index_args, env, timeout_sec=timeout_sec)
    except asyncio.TimeoutError:
        return False, f"Превышен таймаут graphrag index ({int(timeout_sec)} с)."

    if code != 0:
        logger.warning("graphrag_index_failed", code=code, stderr=err[:2000])
        return False, f"graphrag index завершился с кодом {code}: {err or out}"[:4000]

    logger.info("graphrag_index_ok", agent_id=str(agent.id), workspace=str(ws))
    return True, "ok"
