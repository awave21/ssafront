"""Снимок конфигурации агента для помощника-конструктора.

Без снимка советы получаются общими — «создайте функцию» вместо «функция записи
у вас уже есть, но таблицы, куда она пишет, нет». Читаем ровно то, что человек
видит в интерфейсе, и ничего не пишем.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.agent import Agent
from app.db.models.channel import AgentChannel, Channel
from app.db.models.direct_question import DirectQuestion
from app.db.models.directory import Directory
from app.db.models.function_rule import FunctionRule
from app.db.models.knowledge_file import KnowledgeFile
from app.db.models.script_flow import ScriptFlow
from app.db.models.user_table import UserTable

# Снимок целиком уезжает в промпт, поэтому у каждого списка есть потолок:
# агент с сотней правил не должен вытеснить из контекста сам вопрос человека.
MAX_RULES = 40
MAX_TABLES = 20
MAX_COLUMNS = 20
MAX_TITLES = 8

# Функции и сценарии лежат в одной таблице function_rules и различаются только
# триггером: форма функции всегда пишет post_tool (правило срабатывает после
# того, как модель вызвала тул), редактор сценариев — любой другой режим.
FUNCTION_TRIGGER = "post_tool"

# Действия, которые ссылаются на таблицу — по ним понимаем, какие из
# тенантных таблиц этот агент реально трогает.
TABLE_ACTION_TYPES = frozenset({"table_find", "table_write"})


def _rule_kind(rule: FunctionRule) -> str:
    return "function" if rule.trigger_mode == FUNCTION_TRIGGER else "scenario"


def _rule_parameters(rule: FunctionRule) -> list[dict[str, Any]]:
    """Параметры функции — то, что модель заполняет при вызове."""
    schema = (rule.condition_config or {}).get("tool_args_schema")
    if not isinstance(schema, dict):
        return []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    required = schema.get("required")
    required_names = set(required) if isinstance(required, list) else set()

    params: list[dict[str, Any]] = []
    for name, spec in list(properties.items())[:MAX_COLUMNS]:
        spec_dict = spec if isinstance(spec, dict) else {}
        params.append(
            {
                "name": str(name),
                "type": str(spec_dict.get("type") or "string"),
                "description": str(spec_dict.get("description") or "")[:200],
                "required": name in required_names,
            }
        )
    return params


def _referenced_table_ids(rules: list[FunctionRule]) -> set[str]:
    """id таблиц, на которые ссылаются табличные действия правил агента."""
    referenced: set[str] = set()
    for rule in rules:
        for action in rule.actions or []:
            if action.action_type not in TABLE_ACTION_TYPES:
                continue
            table_id = (action.action_config or {}).get("table_id")
            if table_id:
                referenced.add(str(table_id))
    return referenced


async def _load_rules(db: AsyncSession, *, agent_id: UUID, tenant_id: UUID) -> list[FunctionRule]:
    stmt = (
        select(FunctionRule)
        .options(selectinload(FunctionRule.actions), selectinload(FunctionRule.tool))
        .where(
            FunctionRule.tenant_id == tenant_id,
            FunctionRule.agent_id == agent_id,
        )
        .order_by(FunctionRule.priority.asc(), FunctionRule.created_at.asc())
        .limit(MAX_RULES)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _load_tables(db: AsyncSession, *, tenant_id: UUID) -> list[UserTable]:
    # Таблицы принадлежат тенанту, а не агенту: agent_id у user_tables нет.
    stmt = (
        select(UserTable)
        .options(selectinload(UserTable.attributes))
        .where(UserTable.tenant_id == tenant_id, UserTable.is_deleted.is_(False))
        .order_by(UserTable.created_at.asc())
        .limit(MAX_TABLES)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _load_channels(db: AsyncSession, *, agent_id: UUID) -> list[str]:
    # У channels нет ни agent_id, ни tenant_id — изоляция только через агента.
    # Телеграм считаем подключённым лишь при живом вебхуке: строка канала
    # остаётся и после отключения.
    stmt = (
        select(Channel.type)
        .join(AgentChannel, AgentChannel.channel_id == Channel.id)
        .where(
            AgentChannel.agent_id == agent_id,
            Channel.is_deleted.is_(False),
            or_(Channel.type != "telegram", Channel.telegram_webhook_enabled.is_(True)),
        )
    )
    return sorted({row for row in (await db.execute(stmt)).scalars().all() if row})


async def _count(db: AsyncSession, model: Any, *, agent_id: UUID, tenant_id: UUID) -> int:
    stmt = select(func.count()).select_from(model).where(
        model.tenant_id == tenant_id,
        model.agent_id == agent_id,
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def build_agent_snapshot(db: AsyncSession, *, agent: Agent) -> dict[str, Any]:
    """Собрать снимок настроек агента. Только чтение."""
    rules = await _load_rules(db, agent_id=agent.id, tenant_id=agent.tenant_id)
    tables = await _load_tables(db, tenant_id=agent.tenant_id)
    channels = await _load_channels(db, agent_id=agent.id)
    referenced_tables = _referenced_table_ids(rules)

    knowledge_titles_stmt = (
        select(KnowledgeFile.title)
        .where(
            KnowledgeFile.tenant_id == agent.tenant_id,
            KnowledgeFile.agent_id == agent.id,
            KnowledgeFile.type == "file",
        )
        .order_by(KnowledgeFile.order_index.asc())
        .limit(MAX_TITLES)
    )
    knowledge_titles = list((await db.execute(knowledge_titles_stmt)).scalars().all())

    directories_stmt = (
        select(Directory.name)
        .where(
            Directory.tenant_id == agent.tenant_id,
            Directory.agent_id == agent.id,
            Directory.is_deleted.is_(False),
        )
        .limit(MAX_TITLES)
    )
    directories = list((await db.execute(directories_stmt)).scalars().all())

    script_flows_stmt = (
        select(func.count())
        .select_from(ScriptFlow)
        .where(
            ScriptFlow.tenant_id == agent.tenant_id,
            ScriptFlow.agent_id == agent.id,
            ScriptFlow.is_deleted.is_(False),
        )
    )

    return {
        "agent": {
            "name": agent.name,
            "model": agent.model,
            "prompt_chars": len(agent.system_prompt or ""),
            "is_disabled": bool(agent.is_disabled),
            "function_rules_enabled": bool(agent.function_rules_enabled),
            "runtime_bridges_mode": agent.runtime_bridges_mode,
            "sqns_enabled": bool(agent.sqns_enabled),
            "graphrag_enabled": bool(agent.microsoft_graphrag_enabled),
        },
        "rules": [
            {
                "name": rule.name,
                "kind": _rule_kind(rule),
                "enabled": bool(rule.enabled),
                "trigger_mode": rule.trigger_mode,
                "condition_type": rule.condition_type,
                "reaction": rule.reaction_to_execution,
                "behavior": rule.behavior_after_execution,
                "parameters": _rule_parameters(rule),
                "actions": [
                    action.action_type
                    for action in sorted(rule.actions or [], key=lambda a: a.order_index)
                    if action.enabled
                ],
            }
            for rule in rules
        ],
        "tables": [
            {
                "name": table.name,
                "description": (table.description or "")[:200],
                "records_count": table.records_count,
                "used_by_agent": str(table.id) in referenced_tables,
                "columns": [
                    {"name": attr.name, "label": attr.label, "type": attr.attribute_type}
                    for attr in sorted(table.attributes or [], key=lambda a: a.order_index)[
                        :MAX_COLUMNS
                    ]
                ],
            }
            for table in tables
        ],
        "knowledge": {
            "files_count": await _count(
                db, KnowledgeFile, agent_id=agent.id, tenant_id=agent.tenant_id
            ),
            "file_titles": knowledge_titles,
            "direct_questions_count": await _count(
                db, DirectQuestion, agent_id=agent.id, tenant_id=agent.tenant_id
            ),
            "directories": directories,
            "script_flows_count": int((await db.execute(script_flows_stmt)).scalar_one() or 0),
        },
        "channels": channels,
    }


def _render_rule(rule: dict[str, Any]) -> str:
    kind = "функция" if rule["kind"] == "function" else "сценарий"
    state = "включена" if rule["enabled"] else "выключена"
    parts = [f"- {rule['name']} ({kind}, {state})"]
    if rule["kind"] == "function":
        params = ", ".join(param["name"] for param in rule["parameters"]) or "нет"
        parts.append(f"параметры: {params}")
    else:
        parts.append(f"триггер: {rule['trigger_mode']}, условие: {rule['condition_type']}")
    actions = ", ".join(rule["actions"]) or "нет действий"
    parts.append(f"действия: {actions}")
    return "; ".join(parts)


def render_snapshot(snapshot: dict[str, Any]) -> str:
    """Снимок в компактный текст для промпта."""
    agent = snapshot["agent"]
    knowledge = snapshot["knowledge"]

    lines = [
        "# Текущая настройка агента",
        f"Имя: {agent['name']}",
        f"Модель: {agent['model']}",
        f"Системный промпт: {agent['prompt_chars']} символов",
        f"Функции и сценарии включены: {'да' if agent['function_rules_enabled'] else 'нет'}",
        f"Автоблоки в промпте (runtime_bridges_mode): {agent['runtime_bridges_mode']}",
        f"CRM SQNS: {'подключена' if agent['sqns_enabled'] else 'нет'}",
        f"GraphRAG: {'включён' if agent['graphrag_enabled'] else 'нет'}",
        f"Каналы: {', '.join(snapshot['channels']) or 'ни одного'}",
        "",
        "## Функции и сценарии",
    ]
    lines.extend([_render_rule(rule) for rule in snapshot["rules"]] or ["Ни одного правила."])

    lines.append("")
    lines.append("## Таблицы организации")
    if snapshot["tables"]:
        for table in snapshot["tables"]:
            columns = ", ".join(f"{col['name']}:{col['type']}" for col in table["columns"]) or "нет"
            used = "используется этим агентом" if table["used_by_agent"] else "агентом не используется"
            lines.append(
                f"- {table['name']} ({table['records_count']} строк, {used}); колонки: {columns}"
            )
    else:
        lines.append("Ни одной таблицы.")

    lines.extend(
        [
            "",
            "## База знаний",
            f"Документы: {knowledge['files_count']}"
            + (f" ({', '.join(knowledge['file_titles'])})" if knowledge["file_titles"] else ""),
            f"Прямые вопросы: {knowledge['direct_questions_count']}",
            f"Справочники: {', '.join(knowledge['directories']) or 'нет'}",
            f"Скрипт-флоу: {knowledge['script_flows_count']}",
        ]
    )
    return "\n".join(lines)
