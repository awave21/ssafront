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
from app.services.runtime.microsoft_graphrag_neo4j_sync import sync_microsoft_graphrag_workspace_to_neo4j
from app.services.tenant_llm_config import get_decrypted_api_key

logger = structlog.get_logger(__name__)

_PROMPT_TUNE_SKIP = frozenset({"", "off", "false", "none", "no"})

_SEARCH_PROMPTS_RU_DIR = Path(__file__).parent / "search_prompts_ru"
_SEARCH_PROMPT_FILES = (
    "local_search_system_prompt.txt",
    "global_search_map_system_prompt.txt",
    "global_search_reduce_system_prompt.txt",
    "global_search_knowledge_system_prompt.txt",
    "drift_search_system_prompt.txt",
    "drift_reduce_prompt.txt",
    "basic_search_system_prompt.txt",
)

_EXTRACT_PROMPTS_DIR = Path(__file__).parent / "extract_prompts"
# Индексные промпты, которые перекрываем нашей версией поверх дефолтных.
_EXTRACT_PROMPT_FILES = ("extract_graph.txt",)
# Версия шаблона; повышаем при содержательном изменении файла.
_EXTRACT_PROMPT_VERSION = "v1"


def _effective_prompt_tune_language(raw: str | None) -> str | None:
    s = (raw or "").strip()
    if not s or s.lower() in _PROMPT_TUNE_SKIP:
        return None
    return s


def _overlay_extract_prompts(ws: Path) -> int:
    """Перезаписывает индексные промпты (extract_graph) нашей версией.

    `graphrag prompt-tune` подстраивает шаблон под текст корпуса, но не
    формулирует принцип «только конкретные именованные сущности». Наш
    шаблон описывает критерии того, что считать сущностью, чтобы не
    появлялись узлы для обобщённых существительных.

    Версия шаблона хранится в маркере ``.graphrag_extract_prompt_version``:
    после её повышения промпт перезаписывается при следующей пересборке.
    """
    target_dir = ws / "prompts"
    if not target_dir.is_dir() or not _EXTRACT_PROMPTS_DIR.is_dir():
        return 0
    marker = ws / ".graphrag_extract_prompt_version"
    current = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    if current == _EXTRACT_PROMPT_VERSION:
        # Уже на актуальной версии — не трогаем.
        return 0
    overwritten = 0
    for name in _EXTRACT_PROMPT_FILES:
        src = _EXTRACT_PROMPTS_DIR / name
        if not src.is_file():
            continue
        dst = target_dir / name
        try:
            shutil.copyfile(src, dst)
            overwritten += 1
        except OSError as exc:  # noqa: BLE001
            logger.warning("graphrag_extract_prompt_overlay_failed", file=name, error=str(exc))
    if overwritten:
        marker.write_text(_EXTRACT_PROMPT_VERSION + "\n", encoding="utf-8")
        logger.info(
            "graphrag_extract_prompts_overlaid",
            files=overwritten,
            version=_EXTRACT_PROMPT_VERSION,
            workspace=str(ws),
        )
    return overwritten


def _overlay_russian_search_prompts(ws: Path) -> int:
    """Перезаписывает search-промпты в ``<ws>/prompts`` русскими версиями.

    `graphrag prompt-tune` адаптирует только индексные промпты — search-промпты
    остаются на английском. Эта функция накатывает локализованные шаблоны
    из ``search_prompts_ru/`` поверх дефолтных, сохраняя плейсхолдеры
    (``{response_type}``, ``{context_data}``, ``{report_data}``, ``{max_length}``,
    ``{global_query}``, ``{followups}``).
    """
    target_dir = ws / "prompts"
    if not target_dir.is_dir() or not _SEARCH_PROMPTS_RU_DIR.is_dir():
        return 0
    overwritten = 0
    for name in _SEARCH_PROMPT_FILES:
        src = _SEARCH_PROMPTS_RU_DIR / name
        if not src.is_file():
            continue
        dst = target_dir / name
        try:
            shutil.copyfile(src, dst)
            overwritten += 1
        except OSError as exc:  # noqa: BLE001
            logger.warning("graphrag_search_prompt_overlay_failed", file=name, error=str(exc))
    if overwritten:
        logger.info("graphrag_search_prompts_localized", files=overwritten, workspace=str(ws))
    return overwritten


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
        # GraphRAG 3.x may prompt for model/embedding interactively when omitted,
        # which hangs background workers and ends with "Aborted".
        init_args = [
            *prefix,
            "init",
            "--root",
            ".",
            "--force",
            "--model",
            "gpt-4o-mini",
            "--embedding",
            "text-embedding-3-small",
        ]
        code, out, err = await _run_graphrag_subprocess(ws, init_args, env, timeout_sec=min(timeout_sec, 600))
        if code != 0:
            logger.warning("graphrag_init_failed", code=code, stderr=err[:2000])
            return False, f"graphrag init завершился с кодом {code}: {err or out}"[:2000]

    # Идемпотентно перекладываем русские search-промпты поверх дефолтных
    # английских, которые установил `graphrag init`.
    _overlay_russian_search_prompts(ws)

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

    # Перекрываем индексные промпты ПОСЛЕ prompt-tune, чтобы наш шаблон
    # с критериями именованных сущностей пережил автогенерацию.
    _overlay_extract_prompts(ws)

    index_args = [*prefix, "index", "--root", "."]
    try:
        code, out, err = await _run_graphrag_subprocess(ws, index_args, env, timeout_sec=timeout_sec)
    except asyncio.TimeoutError:
        return False, f"Превышен таймаут graphrag index ({int(timeout_sec)} с)."

    if code != 0:
        logger.warning("graphrag_index_failed", code=code, stderr=err[:2000])
        return False, f"graphrag index завершился с кодом {code}: {err or out}"[:4000]

    neo4j_ok, neo4j_msg = await sync_microsoft_graphrag_workspace_to_neo4j(
        settings=settings,
        agent=agent,
        tenant_id=agent.tenant_id,
    )
    if not neo4j_ok:
        return False, f"graphrag index выполнен, но sync в Neo4j не удался: {neo4j_msg}"[:4000]

    logger.info("graphrag_index_ok", agent_id=str(agent.id), workspace=str(ws))
    return True, "ok"
