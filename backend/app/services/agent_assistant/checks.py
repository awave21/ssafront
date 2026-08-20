"""Проверка настроек агента: что сохранено, но работать не будет.

Считает КОД, а не модель. Урок этой сессии: как только модель сама сверяет
списки, она уверенно называет отсутствующим то, что лежит у неё в контексте.
Помощнику отдаём готовый список находок, его дело — объяснить их человеку.

Каждая находка обязана быть однозначной: не «стоит подумать», а «сохранено,
но не сработает, вот почему».
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.agent import Agent
from app.db.models.channel import AgentChannel, Channel
from app.db.models.direct_question import DirectQuestion
from app.db.models.directory import Directory, DirectoryItem
from app.db.models.function_rule import FunctionRule
from app.db.models.knowledge_file import KnowledgeFile
from app.db.models.model_pricing import ModelPricing
from app.db.models.user_table import UserTable
from app.services.tenant_llm_config import get_decrypted_api_key

LEVELS = ("critical", "warning", "hint")

TABLE_ACTIONS = frozenset({"table_find", "table_write"})


@dataclass(slots=True)
class Finding:
    """Одна находка. level: critical — не работает; warning — работает плохо."""

    level: str
    title: str
    detail: str


def _text(config: dict[str, Any] | None, *keys: str) -> str:
    for key in keys:
        value = (config or {}).get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


async def _check_rules(
    db: AsyncSession, agent: Agent, tables: dict[str, UserTable]
) -> list[Finding]:
    stmt = (
        select(FunctionRule)
        .options(selectinload(FunctionRule.actions), selectinload(FunctionRule.tool))
        .where(FunctionRule.tenant_id == agent.tenant_id, FunctionRule.agent_id == agent.id)
    )
    rules = list((await db.execute(stmt)).scalars().all())
    findings: list[Finding] = []

    for rule in rules:
        if not rule.enabled:
            continue
        where = f"правило «{rule.name}»"
        config = rule.condition_config or {}

        if rule.condition_type == "keyword" and not (config.get("keywords") or []):
            findings.append(
                Finding("critical", f"{where}: условие по ключевым словам без слов",
                        "Список слов пуст — условие не совпадёт ни разу.")
            )
        if rule.condition_type == "regex":
            pattern = _text(config, "pattern", "regex")
            if not pattern:
                findings.append(
                    Finding("critical", f"{where}: регулярное выражение не задано",
                            "Шаблон пуст — условие не совпадёт ни разу.")
                )
            else:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    findings.append(
                        Finding("critical", f"{where}: битое регулярное выражение",
                                f"Шаблон не компилируется: {exc}. Условие не совпадёт ни разу.")
                    )

        enabled_actions = [a for a in (rule.actions or []) if a.enabled]
        if rule.reaction_to_execution == "silent" and not enabled_actions:
            findings.append(
                Finding("critical", f"{where}: молчит и ничего не делает",
                        "Реакция «Промолчать» и ни одного действия — агент просто перестаёт отвечать.")
            )

        for action in enabled_actions:
            findings.extend(_check_action(where, action, tables))

        if rule.tool is not None:
            tool = rule.tool
            if tool.is_deleted or tool.status != "active":
                findings.append(
                    Finding("critical", f"{where}: инструмент недоступен",
                            f"Инструмент «{tool.name}» удалён или не активен — вызов не состоится.")
                )
            elif not (tool.description or "").strip():
                findings.append(
                    Finding("warning", f"{where}: у функции пустое описание",
                            "Модель решает по описанию, когда звать функцию. Без него не позовёт.")
                )

        schema = config.get("tool_args_schema")
        properties = schema.get("properties") if isinstance(schema, dict) else None
        if isinstance(properties, dict):
            blank = [
                name
                for name, spec in properties.items()
                if not str((spec or {}).get("description") or "").strip()
            ]
            if blank:
                findings.append(
                    Finding("warning", f"{where}: параметры без описания",
                            "Модель заполняет их наугад: " + ", ".join(sorted(blank)[:5]))
                )

    return findings


def _check_action(where: str, action: Any, tables: dict[str, UserTable]) -> list[Finding]:
    config = action.action_config or {}
    kind = action.action_type
    findings: list[Finding] = []

    if kind in TABLE_ACTIONS:
        table_id = str(config.get("table_id") or "").strip()
        if not table_id:
            findings.append(
                Finding("critical", f"{where}: действие с таблицей без таблицы",
                        "Таблица не выбрана — при срабатывании действие упадёт.")
            )
            return findings
        table = tables.get(table_id)
        if table is None:
            findings.append(
                Finding("critical", f"{where}: таблицы больше нет",
                        "Действие ссылается на удалённую таблицу — при срабатывании упадёт.")
            )
            return findings

        columns = {attr.name for attr in (table.attributes or [])}
        if kind == "table_find":
            column = _text(config, "column", "search_column")
            if not column:
                findings.append(
                    Finding("critical", f"{where}: поиск в таблице без колонки",
                            "Не выбрано, по какой колонке искать.")
                )
            elif column not in columns:
                findings.append(
                    Finding("critical", f"{where}: колонки «{column}» нет в таблице",
                            f"В таблице «{table.name}» такой колонки не существует.")
                )
        else:
            values = config.get("values")
            if not isinstance(values, dict) or not values:
                findings.append(
                    Finding("warning", f"{where}: запись в таблицу без значений",
                            "Не задано ни одного поля — строка получится пустой.")
                )
            else:
                unknown = [name for name in values if name not in columns]
                if unknown:
                    findings.append(
                        Finding("critical", f"{where}: полей нет в таблице",
                                f"Значения молча выбросятся: {', '.join(sorted(unknown)[:5])}")
                    )
            if str(config.get("mode") or "insert") in {"update", "upsert"} and not _text(
                config, "match_column"
            ):
                findings.append(
                    Finding("critical", f"{where}: обновление строки без колонки сопоставления",
                            "Непонятно, какую строку обновлять.")
                )
        return findings

    if kind == "set_variable" and not _text(config, "name"):
        findings.append(
            Finding("warning", f"{where}: переменная без имени", "Значение некуда записать.")
        )
    if kind == "augment_prompt" and not _text(config, "instruction", "prompt"):
        findings.append(
            Finding("warning", f"{where}: дополнение промпта пустое", "Модель ничего не получит.")
        )
    if kind == "send_message" and not _text(config, "text", "message"):
        findings.append(
            Finding("warning", f"{where}: сообщение без текста", "Клиенту нечего отправить.")
        )
    return findings


async def _check_knowledge(db: AsyncSession, agent: Agent) -> list[Finding]:
    findings: list[Finding] = []
    scope = {"tenant_id": agent.tenant_id, "agent_id": agent.id}

    files = list(
        (
            await db.execute(
                select(KnowledgeFile.title, KnowledgeFile.vector_status).where(
                    KnowledgeFile.tenant_id == scope["tenant_id"],
                    KnowledgeFile.agent_id == scope["agent_id"],
                    KnowledgeFile.type == "file",
                    KnowledgeFile.is_enabled.is_(True),
                    KnowledgeFile.vector_status != "indexed",
                )
            )
        ).all()
    )
    if files:
        names = ", ".join(f"«{title}» ({status})" for title, status in files[:5])
        findings.append(
            Finding("critical", f"Документов не проиндексировано: {len(files)}",
                    f"По ним поиск не работает. {names}")
        )

    total, enabled, no_vector = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(DirectQuestion.is_enabled.is_(True)),
                func.count().filter(
                    DirectQuestion.is_enabled.is_(True), DirectQuestion.embedding.is_(None)
                ),
            ).where(
                DirectQuestion.tenant_id == scope["tenant_id"],
                DirectQuestion.agent_id == scope["agent_id"],
            )
        )
    ).one()
    if total and not enabled:
        findings.append(
            Finding("warning", f"Прямые вопросы заведены ({total}), но все выключены",
                    "Поиск по ним ничего не найдёт, пока они выключены.")
        )
    if no_vector:
        findings.append(
            Finding("critical", f"Прямых вопросов без эмбеддинга: {no_vector}",
                    "Включены, но не находятся никогда — нужна переиндексация.")
        )

    directories = list(
        (
            await db.execute(
                select(
                    Directory.name,
                    Directory.search_type,
                    func.count(DirectoryItem.id).label("items"),
                    func.count(DirectoryItem.embedding).label("vectors"),
                )
                .outerjoin(DirectoryItem, DirectoryItem.directory_id == Directory.id)
                .where(
                    Directory.tenant_id == scope["tenant_id"],
                    Directory.agent_id == scope["agent_id"],
                    Directory.is_deleted.is_(False),
                    Directory.is_enabled.is_(True),
                )
                .group_by(Directory.id, Directory.name, Directory.search_type)
            )
        ).all()
    )
    for name, search_type, items, vectors in directories:
        if not items:
            findings.append(
                Finding("critical", f"Справочник «{name}» включён, но пуст",
                        "Пустой справочник не подключается к агенту как инструмент.")
            )
        elif search_type == "semantic" and vectors < items:
            findings.append(
                Finding("critical", f"Справочник «{name}»: записей без вектора {items - vectors}",
                        "Смысловой поиск их не найдёт — нужна переиндексация.")
            )
    return findings


async def _check_agent(db: AsyncSession, agent: Agent) -> list[Finding]:
    findings: list[Finding] = []

    if not (agent.system_prompt or "").strip():
        findings.append(
            Finding("critical", "Системный промпт пуст",
                    "Агент не знает, кто он и что делает.")
        )

    if not await get_decrypted_api_key(db, agent.tenant_id, "openai"):
        findings.append(
            Finding("critical", "У организации не задан ключ OpenAI",
                    "Молча не работают эмбеддинги: поиск по знаниям, прямым вопросам и справочникам.")
        )

    bare_model = (agent.model or "").split(":")[-1]
    known = (
        await db.execute(
            select(func.count()).select_from(ModelPricing).where(
                ModelPricing.model_name == bare_model, ModelPricing.is_active.is_(True)
            )
        )
    ).scalar_one()
    if not known:
        findings.append(
            Finding("warning", f"Модель «{agent.model}» не заведена в тарифах",
                    "Расход по агенту не посчитается и не попадёт в баланс.")
        )

    if agent.sqns_enabled and not agent.sqns_configured:
        findings.append(
            Finding("critical", "CRM SQNS включена, но не настроена",
                    "Инструменты записи не заработают.")
        )
    if getattr(agent, "sqns_error", None):
        findings.append(
            Finding("warning", "CRM SQNS сообщает об ошибке", str(agent.sqns_error)[:200])
        )
    if agent.microsoft_graphrag_enabled and not agent.microsoft_graphrag_last_indexed_at:
        findings.append(
            Finding("warning", "GraphRAG включён, но индекс ни разу не строился",
                    "Поиск по графу вернёт пустоту.")
        )

    stale_telegram = (
        await db.execute(
            select(func.count())
            .select_from(Channel)
            .join(AgentChannel, AgentChannel.channel_id == Channel.id)
            .where(
                AgentChannel.agent_id == agent.id,
                Channel.is_deleted.is_(False),
                Channel.type == "telegram",
                or_(
                    Channel.telegram_webhook_enabled.is_(False),
                    Channel.telegram_webhook_enabled.is_(None),
                ),
            )
        )
    ).scalar_one()
    if stale_telegram:
        findings.append(
            Finding("critical", "Telegram подключён, но вебхук выключен",
                    "Сообщения от клиентов до агента не доходят.")
        )
    return findings


async def run_setup_checks(db: AsyncSession, *, agent: Agent) -> list[Finding]:
    """Все проверки настроек агента. Только чтение."""
    tables = {
        str(table.id): table
        for table in (
            await db.execute(
                select(UserTable)
                .options(selectinload(UserTable.attributes))
                .where(UserTable.tenant_id == agent.tenant_id, UserTable.is_deleted.is_(False))
            )
        ).scalars()
    }

    findings: list[Finding] = []
    findings.extend(await _check_rules(db, agent, tables))
    findings.extend(await _check_knowledge(db, agent))
    findings.extend(await _check_agent(db, agent))
    findings.sort(key=lambda f: LEVELS.index(f.level) if f.level in LEVELS else len(LEVELS))
    return findings


def render_checks(findings: list[Finding]) -> str:
    """Находки в текст для промпта."""
    if not findings:
        return (
            "## Проверка настроек\n"
            "Проблем не нашлось. Это проверка по настройкам, а не по качеству ответов: "
            "агент может быть настроен верно и всё равно отвечать плохо."
        )

    titles = {"critical": "Не работает", "warning": "Работает плохо", "hint": "Стоит улучшить"}
    lines = ["## Проверка настроек"]
    for level in LEVELS:
        group = [f for f in findings if f.level == level]
        if not group:
            continue
        lines.append(f"### {titles[level]}")
        lines.extend(f"- {f.title}: {f.detail}" for f in group)
    lines.append(
        "Список посчитан по базе и уже готов — не добавляй в него своих догадок "
        "и не переформулируй находки так, будто проверил сам."
    )
    return "\n".join(lines)
