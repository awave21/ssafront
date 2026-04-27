"""Текстовый корпус для индексации графа знаний (SQNS, сценарии, БЗ, справочники)."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.directory import Directory, DirectoryItem
from app.db.models.knowledge_file import KnowledgeFile
from app.db.models.script_flow import ScriptFlow
from app.db.models.sqns_service import (
    SqnsEmployee,
    SqnsResource,
    SqnsService,
    SqnsServiceCategory,
    SqnsServiceResource,
)
from app.services.script_flow_compiler import compile_script_flow_to_text
from app.services.script_flow_sqns_profiles import build_sqns_profile_lookup

_TAG_RE = re.compile(r"<[^>]+>")

# Убираем из текста корпуса имена/URL продукта индексации — иначе LLM выделяет лишние сущности (БЗ, сценарии).
_INDEXER_VENDOR_RE = re.compile(
    r"https?://[^\s\)\]\>\"']*graphrag[^\s\)\]\>\"']*"
    r"|github\.com/microsoft/graphrag[^\s\)\]\>\"']*"
    r"|Microsoft\s+GraphRAG"
    r"|query_microsoft_graphrag"
    r"|microsoft_graphrag\w*"
    r"|MICROSOFT[_\s]?GRAPHRAG[A-Z0-9_]*"
    r"|\bGraphRAG\b"
    r"|\bgraphrag\b",
    re.IGNORECASE,
)


def _strip_indexer_vendor_mentions(text: str) -> str:
    if not text:
        return text
    out = _INDEXER_VENDOR_RE.sub(" ", text)
    return re.sub(r"[ \t]{2,}", " ", out)


def sanitize_rich_text(value: str | None) -> str:
    if not value:
        return ""
    text = _TAG_RE.sub(" ", str(value))
    return re.sub(r"\s+", " ", text).strip()


def _fmt_price(value: Decimal | None) -> str:
    if value is None:
        return ""
    try:
        return f"{round(float(value), 2):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _duration_minutes(seconds: int | None) -> str:
    if seconds is None or seconds <= 0:
        return ""
    m = max(1, round(seconds / 60))
    return f"{m} мин"


def _corpus_bytes_from_sections(sections: dict[str, str], *, agent_id: UUID) -> tuple[bytes, str]:
    ordered_keys = [
        "input/01_categories.txt",
        "input/02_services.txt",
        "input/03_specialists.txt",
        "input/04_relations.txt",
        "input/05_employees_crm.txt",
        "input/06_script_flows.txt",
        "input/07_knowledge_files.txt",
        "input/08_directories.txt",
    ]
    parts: list[str] = []
    for key in ordered_keys:
        if key not in sections:
            continue
        parts.append(f"###GRAPH_SECTION:<{key}>###\n")
        chunk = sections[key]
        parts.append(chunk if chunk.endswith("\n") else chunk + "\n")
    for key, val in sorted(sections.items()):
        if key in ordered_keys:
            continue
        parts.append(f"###GRAPH_SECTION:<{key}>###\n")
        parts.append(val if val.endswith("\n") else val + "\n")
    body = "".join(parts).encode("utf-8")
    return body, f"graphrag-agent-corpus-{agent_id}.txt"


def write_graphrag_sections_to_workspace(ws: Path, sections: dict[str, str]) -> None:
    for rel, text in sections.items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    legacy_readme = ws / "input" / "00_README.txt"
    if legacy_readme.is_file():
        legacy_readme.unlink()


async def gather_sqns_graphrag_sections(
    db: AsyncSession,
    agent_id: UUID,
    *,
    active_sqns_only: bool = True,
) -> dict[str, str]:
    """Секции ``input/*.txt`` из таблиц ``sqns_*`` (те же данные, что и у тулов вроде ``sqns_list_resources``). Сотрудники: ``sqns_employees`` по ``external_id`` отобранных ``sqns_resources``."""
    sections: dict[str, str] = {}

    cat_stmt = (
        select(SqnsServiceCategory)
        .where(
            SqnsServiceCategory.agent_id == agent_id,
            SqnsServiceCategory.is_enabled.is_(True),
            SqnsServiceCategory.deleted_at.is_(None),
        )
        .order_by(SqnsServiceCategory.priority.desc(), SqnsServiceCategory.name)
    )
    categories = (await db.execute(cat_stmt)).scalars().all()

    svc_stmt = select(SqnsService).where(
        SqnsService.agent_id == agent_id,
        SqnsService.is_enabled.is_(True),
        SqnsService.stale_since.is_(None),
    )
    services = (await db.execute(svc_stmt.order_by(SqnsService.priority.desc(), SqnsService.name))).scalars().all()

    res_stmt = select(SqnsResource).where(
        SqnsResource.agent_id == agent_id,
        SqnsResource.active.is_(True),
        SqnsResource.is_active.is_(True),
    )
    specialists = (await db.execute(res_stmt.order_by(SqnsResource.name))).scalars().all()

    service_ids = {s.id for s in services}
    resource_ids = {r.id for r in specialists}

    links: list[SqnsServiceResource] = []
    if service_ids:
        link_stmt = select(SqnsServiceResource).where(SqnsServiceResource.service_id.in_(service_ids))
        links = list((await db.execute(link_stmt)).scalars().all())

    active_category_names: set[str] = set()
    for s in services:
        if s.category and str(s.category).strip():
            active_category_names.add(str(s.category).strip())

    lines_cat: list[str] = ["# Категории услуг (sqns_service_categories)", ""]
    for c in categories:
        if active_category_names and c.name not in active_category_names:
            continue
        lines_cat.append(f"- {sanitize_rich_text(c.name)} (приоритет {c.priority})")
    sections["input/01_categories.txt"] = "\n".join(lines_cat) if len(lines_cat) > 2 else "\n".join(lines_cat + ["(нет категорий)"])

    lines_svc: list[str] = ["# Услуги (sqns_services)", ""]
    for s in services:
        price = _fmt_price(s.price)
        dur = _duration_minutes(s.duration_seconds)
        desc = sanitize_rich_text(s.description)
        bits = [f"## {sanitize_rich_text(s.name)} (external_id={s.external_id})"]
        if s.category:
            bits.append(f"Категория: {sanitize_rich_text(s.category)}")
        if price:
            bits.append(f"Цена: {price}")
        if dur:
            bits.append(f"Длительность: ~{dur}")
        if desc:
            bits.append(f"Описание: {desc}")
        lines_svc.extend(bits + [""])
    sections["input/02_services.txt"] = "\n".join(lines_svc) if len(lines_svc) > 2 else "\n".join(lines_svc + ["(нет услуг)"])

    lines_spec: list[str] = ["# Специалисты (sqns_resources)", ""]
    for r in specialists:
        info = sanitize_rich_text(r.information)
        lines_spec.append(
            f"## {sanitize_rich_text(r.name)} (external_id={r.external_id}, uuid={r.id})\n"
            f"Роль/специализация: {sanitize_rich_text(r.specialization) or '—'}\n"
            f"Доп. информация: {info or '—'}\n"
        )
    sections["input/03_specialists.txt"] = (
        "\n".join(lines_spec) if len(lines_spec) > 2 else "\n".join(lines_spec + ["(нет специалистов)"])
    )

    lines_rel: list[str] = ["# Связи услуга — специалист", ""]
    for link in links:
        if link.resource_id not in resource_ids:
            continue
        lines_rel.append(
            f"- service_db_id={link.service_id} → specialist_db_id={link.resource_id} "
            f"(override_duration_sec={link.duration_seconds})"
        )
    sections["input/04_relations.txt"] = (
        "\n".join(lines_rel) if len(lines_rel) > 2 else "\n".join(lines_rel + ["(нет связей)"])
    )

    specialist_external_ids = {r.external_id for r in specialists}
    emp_stmt = select(SqnsEmployee).where(SqnsEmployee.agent_id == agent_id)
    if specialist_external_ids:
        emp_stmt = emp_stmt.where(SqnsEmployee.external_id.in_(specialist_external_ids))
    else:
        emp_stmt = emp_stmt.where(false())
    if active_sqns_only:
        emp_stmt = emp_stmt.where(SqnsEmployee.is_fired.is_(False), SqnsEmployee.is_deleted.is_(False))
    employees = (await db.execute(emp_stmt.order_by(SqnsEmployee.full_name))).scalars().all()
    lines_emp: list[str] = ["# Сотрудники (sqns_employees)", ""]
    for e in employees:
        lines_emp.append(
            f"## {sanitize_rich_text(e.full_name)} (external_id={e.external_id})\n"
            f"Должность: {sanitize_rich_text(e.position) or '—'}\n"
        )
    sections["input/05_employees_crm.txt"] = (
        "\n".join(lines_emp) if len(lines_emp) > 2 else "\n".join(lines_emp + ["(нет записей)"])
    )

    flow_stmt = (
        select(ScriptFlow)
        .where(ScriptFlow.agent_id == agent_id, ScriptFlow.flow_status == "published")
        .order_by(ScriptFlow.updated_at.desc())
    )
    flows = (await db.execute(flow_stmt)).scalars().all()
    lines_sf: list[str] = ["# Опубликованные сценарии (script flows)", ""]
    for flow in flows:
        profile_lookup = await build_sqns_profile_lookup(db, agent_id=agent_id, flow_definition=flow.flow_definition or {})
        compiled = compile_script_flow_to_text(
            name=flow.name,
            flow_metadata=flow.flow_metadata or {},
            flow_definition=flow.flow_definition or {},
            profile_lookup=profile_lookup,
        )
        lines_sf.append(f"## {sanitize_rich_text(flow.name)} (id={flow.id})\n\n{compiled}\n")
    sections["input/06_script_flows.txt"] = (
        "\n".join(lines_sf) if len(lines_sf) > 2 else "\n".join(lines_sf + ["(нет опубликованных сценариев)"])
    )

    k_stmt = (
        select(KnowledgeFile)
        .where(
            KnowledgeFile.agent_id == agent_id,
            KnowledgeFile.type == "file",
            KnowledgeFile.is_enabled.is_(True),
        )
        .order_by(KnowledgeFile.order_index, KnowledgeFile.title)
    )
    kfiles = (await db.execute(k_stmt)).scalars().all()
    lines_kn: list[str] = ["# Файлы базы знаний", ""]
    for f in kfiles:
        body = sanitize_rich_text(f.content)[:120_000]
        lines_kn.append(f"## {sanitize_rich_text(f.title)} (id={f.id})\n{body}\n")
    sections["input/07_knowledge_files.txt"] = (
        "\n".join(lines_kn) if len(lines_kn) > 2 else "\n".join(lines_kn + ["(нет файлов)"])
    )

    d_stmt = (
        select(Directory)
        .options(selectinload(Directory.items))
        .where(
            Directory.agent_id == agent_id,
            Directory.is_enabled.is_(True),
            Directory.is_deleted.is_(False),
        )
        .order_by(Directory.name)
    )
    dirs = (await db.execute(d_stmt)).scalars().all()
    lines_dir: list[str] = ["# Справочники", ""]
    for d in dirs:
        lines_dir.append(f"## {sanitize_rich_text(d.name)} (slug={d.slug}, template={d.template})\n")
        for item in d.items[:5000]:
            try:
                lines_dir.append(json.dumps(item.data, ensure_ascii=False)[:8000])
            except (TypeError, ValueError):
                lines_dir.append(str(item.data)[:8000])
        lines_dir.append("")
    sections["input/08_directories.txt"] = (
        "\n".join(lines_dir) if len(lines_dir) > 2 else "\n".join(lines_dir + ["(нет справочников)"])
    )

    for key, val in list(sections.items()):
        sections[key] = _strip_indexer_vendor_mentions(val)

    return sections


async def build_sqns_graphrag_corpus(
    db: AsyncSession,
    agent_id: UUID,
    *,
    active_sqns_only: bool = True,
) -> tuple[bytes, str]:
    sections = await gather_sqns_graphrag_sections(db, agent_id, active_sqns_only=active_sqns_only)
    return _corpus_bytes_from_sections(sections, agent_id=agent_id)
