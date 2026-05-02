"""Stage 3: post-run heuristic scoring of whether the LLM applied a tactic.

For each recently-completed run that called `search_expert_tactics`, find the
unscored log row, fetch the matched tactic's preferred/forbidden phrases and
required followup question, and check the agent's final response.

Heuristics:
- applied      = response contains ≥1 preferred phrase (substring, case-insensitive)
- violation    = response contains ≥1 forbidden phrase
- followup_asked = response contains the required followup question (or its
                   significant tokens — same prefix-token approach as enrich.py)
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.run import Run
from app.db.models.script_flow_node_index import ScriptFlowNodeIndex
from app.db.models.script_flow_tactic_search import ScriptFlowTacticSearch

log = structlog.get_logger(__name__)

PREFIX_LEN = 6
TOKEN_MIN_LEN = 5


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def _tokens(s: str) -> list[str]:
    raw = re.findall(r"[\wа-яА-ЯёЁ]+", (s or "").lower())
    return [t[:PREFIX_LEN] for t in raw if len(t) >= TOKEN_MIN_LEN]


def _contains_phrase(haystack: str, phrase: str) -> bool:
    if not phrase:
        return False
    h = _normalize(haystack)
    p = _normalize(phrase)
    if not p:
        return False
    if p in h:
        return True
    # Token-prefix match: ≥60% of phrase's significant tokens present in haystack
    p_toks = _tokens(p)
    if len(p_toks) < 2:
        return False
    h_toks = set(_tokens(h))
    hits = sum(1 for t in p_toks if t in h_toks)
    return hits / len(p_toks) >= 0.6


def _extract_assistant_text(messages: Any) -> str:
    """Extract the final assistant text response from the run's messages JSON."""
    if not messages:
        return ""
    msgs = messages if isinstance(messages, list) else json.loads(messages)
    parts: list[str] = []
    for m in reversed(msgs):
        kind = m.get("kind") if isinstance(m, dict) else None
        if kind == "response":
            for p in m.get("parts") or []:
                pk = p.get("part_kind")
                if pk == "text":
                    text = (p.get("content") or "").strip()
                    if text:
                        parts.append(text)
            if parts:
                break
    return "\n".join(parts)


async def score_recent_runs(
    db: AsyncSession,
    *,
    lookback_minutes: int = 30,
    limit: int = 200,
) -> int:
    """Score unscored tactic searches whose runs completed recently.

    Returns the number of rows updated.
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)

    pending = (
        await db.execute(
            select(ScriptFlowTacticSearch)
            .where(
                ScriptFlowTacticSearch.run_scored_at.is_(None),
                ScriptFlowTacticSearch.created_at >= since,
            )
            .order_by(ScriptFlowTacticSearch.created_at.asc())
            .limit(limit)
        )
    ).scalars().all()

    if not pending:
        return 0

    # Pre-fetch tactic phrases — group by node_id to avoid N+1
    node_ids = {p.top_node_id for p in pending if p.top_node_id}
    agent_ids = {p.agent_id for p in pending}
    tactic_map: dict[tuple[UUID, str], ScriptFlowNodeIndex] = {}
    if node_ids and agent_ids:
        nodes = (
            await db.execute(
                select(ScriptFlowNodeIndex).where(
                    ScriptFlowNodeIndex.agent_id.in_(agent_ids),
                    ScriptFlowNodeIndex.node_id.in_(node_ids),
                )
            )
        ).scalars().all()
        for n in nodes:
            tactic_map[(n.agent_id, n.node_id)] = n

    updated = 0
    now = datetime.now(timezone.utc)

    for row in pending:
        # Find a run from the same agent right after the search
        run_q = (
            select(Run)
            .where(
                Run.agent_id == row.agent_id,
                Run.created_at >= row.created_at - timedelta(seconds=10),
                Run.created_at <= row.created_at + timedelta(minutes=5),
                Run.status == "succeeded",
            )
            .order_by(Run.created_at.asc())
            .limit(1)
        )
        run = (await db.execute(run_q)).scalar_one_or_none()

        # Mark as scored even if run not found, so we don't reprocess forever
        applied: bool | None = None
        violation: bool | None = None
        followup: bool | None = None
        excerpt: str | None = None

        if run is not None and row.top_node_id:
            response_text = (
                _extract_assistant_text(run.messages)
                or (run.output_message or "")
            ).strip()

            if response_text:
                excerpt = response_text[:600]
                tactic = tactic_map.get((row.agent_id, row.top_node_id))
                if tactic is not None:
                    preferred = list(tactic.preferred_phrases or [])
                    forbidden = list(tactic.forbidden_phrases or [])
                    followup_q = (tactic.required_followup_question or "").strip()

                    applied = any(
                        _contains_phrase(response_text, p) for p in preferred if p
                    )
                    violation = any(
                        _contains_phrase(response_text, p) for p in forbidden if p
                    )
                    followup = (
                        _contains_phrase(response_text, followup_q)
                        if followup_q else None
                    )

        await db.execute(
            update(ScriptFlowTacticSearch)
            .where(ScriptFlowTacticSearch.id == row.id)
            .values(
                run_scored_at=now,
                applied=applied,
                violation=violation,
                followup_asked=followup,
                agent_response_excerpt=excerpt,
                run_id=run.id if run is not None else row.run_id,
            )
        )
        updated += 1

    await db.commit()
    log.info("script_flow_application_scorer.run", scored=updated)
    return updated
