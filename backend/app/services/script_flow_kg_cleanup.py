"""Remove references to a deleted KG entity from all script flows of an agent."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.script_flow import ScriptFlow

_LINK_LIST_KEYS = (
    "motive_ids",
    "argument_ids",
    "proof_ids",
    "objection_ids",
    "constraint_ids",
)


def _strip_kg_links(links: dict[str, Any], entity_id: str) -> bool:
    changed = False
    eid = str(entity_id)
    for k in _LINK_LIST_KEYS:
        vals = links.get(k)
        if not isinstance(vals, list):
            continue
        new_vals = [x for x in vals if str(x) != eid]
        if len(new_vals) != len(vals):
            links[k] = new_vals
            changed = True
    oid = links.get("outcome_id")
    if oid is not None and str(oid) == eid:
        links["outcome_id"] = None
        changed = True
    return changed


def strip_entity_from_flow_definition(
    flow_definition: dict[str, Any],
    *,
    entity_id: str,
) -> tuple[dict[str, Any], bool]:
    """Returns a deep-copied flow_definition with kg_links scrubbed; flag if changed."""
    import copy

    fd = copy.deepcopy(flow_definition)
    changed = False
    nodes = fd.get("nodes")
    if not isinstance(nodes, list):
        return fd, False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        data = n.get("data")
        if not isinstance(data, dict):
            continue
        links = data.get("kg_links")
        if not isinstance(links, dict):
            continue
        if _strip_kg_links(links, entity_id):
            changed = True
    return fd, changed


async def strip_kg_entity_from_all_agent_flows(
    db: AsyncSession,
    *,
    agent_id: UUID,
    tenant_id: UUID,
    entity_id: UUID,
) -> int:
    """Update all flows for the agent; returns number of rows updated."""
    stmt = select(ScriptFlow).where(
        ScriptFlow.agent_id == agent_id,
        ScriptFlow.tenant_id == tenant_id,
    )
    flows = list((await db.execute(stmt)).scalars().all())
    eid = str(entity_id)
    updated = 0
    for flow in flows:
        fd = flow.flow_definition if isinstance(flow.flow_definition, dict) else {}
        new_fd, changed = strip_entity_from_flow_definition(fd, entity_id=eid)
        if changed:
            flow.flow_definition = new_fd
            updated += 1
    if updated:
        await db.commit()
    return updated
