"""Загрузка текстов профилей SQNS для enrich-at-publish compiled_text."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsResource, SqnsService


async def build_sqns_profile_lookup(
    db: AsyncSession,
    *,
    agent_id: UUID,
    flow_definition: dict[str, Any],
) -> dict[str, str]:
    """
    Ключ: \"employee:<uuid>\" / \"service:<uuid>\" — как в compile_script_flow_to_text.
    """
    nodes = flow_definition.get("nodes")
    if not isinstance(nodes, list):
        return {}

    emp_ids: set[UUID] = set()
    svc_ids: set[UUID] = set()
    for n in nodes:
        if not isinstance(n, dict):
            continue
        d = n.get("data")
        if not isinstance(d, dict):
            continue
        if d.get("node_type") != "business_rule":
            continue
        et = str(d.get("entity_type") or "").lower()
        eid = d.get("entity_id")
        if not eid:
            continue
        try:
            uid = UUID(str(eid))
        except (TypeError, ValueError):
            continue
        if et == "employee":
            emp_ids.add(uid)
        elif et == "service":
            svc_ids.add(uid)

    out: dict[str, str] = {}
    if emp_ids:
        stmt = select(SqnsResource).where(
            SqnsResource.id.in_(emp_ids),
            SqnsResource.agent_id == agent_id,
        )
        for row in (await db.execute(stmt)).scalars().all():
            if row.information and str(row.information).strip():
                out[f"employee:{row.id}"] = str(row.information).strip()
    if svc_ids:
        stmt = select(SqnsService).where(
            SqnsService.id.in_(svc_ids),
            SqnsService.agent_id == agent_id,
        )
        for row in (await db.execute(stmt)).scalars().all():
            if row.description and str(row.description).strip():
                out[f"service:{row.id}"] = str(row.description).strip()
    return out
