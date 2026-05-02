"""Coverage analytics for `search_expert_tactics` tool calls.

Aggregates the `script_flow_tactic_searches` log into actionable signals for
the agent's owner: which tactics are getting hit, which queries return weak
matches (potential coverage gaps), and which queries returned nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.script_flow_tactic_search import ScriptFlowTacticSearch

# Cosine similarity above this is "good enough" — LLM can rely on the tactic.
RELEVANCE_HIGH_THRESHOLD = 0.70
# Below this — irrelevant match (gap).
RELEVANCE_LOW_THRESHOLD = 0.55


@dataclass
class CoverageSummary:
    total_searches: int = 0
    relevant_count: int = 0      # top_score >= HIGH
    weak_count: int = 0          # LOW < top_score < HIGH
    irrelevant_count: int = 0    # top_score <= LOW
    no_match_count: int = 0      # 0 hits
    distinct_tactics_used: int = 0


@dataclass
class TopTactic:
    node_id: str
    title: str | None
    hit_count: int
    avg_score: float
    applied_count: int = 0
    violation_count: int = 0
    followup_count: int = 0
    scored_count: int = 0


@dataclass
class GapQuery:
    query: str
    top_title: str | None
    top_score: float | None
    created_at: datetime
    occurrences: int = 1


@dataclass
class CoverageReport:
    period_days: int
    summary: CoverageSummary = field(default_factory=CoverageSummary)
    top_tactics: list[TopTactic] = field(default_factory=list)
    gap_queries: list[GapQuery] = field(default_factory=list)
    no_match_queries: list[GapQuery] = field(default_factory=list)


async def build_coverage_report(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    period_days: int = 7,
    top_n_tactics: int = 10,
    top_n_gaps: int = 20,
) -> CoverageReport:
    since = datetime.now(timezone.utc) - timedelta(days=period_days)

    base = (
        select(ScriptFlowTacticSearch)
        .where(
            ScriptFlowTacticSearch.tenant_id == tenant_id,
            ScriptFlowTacticSearch.agent_id == agent_id,
            ScriptFlowTacticSearch.created_at >= since,
        )
    )

    # Summary aggregates
    total_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_q)).scalar_one() or 0

    if total == 0:
        return CoverageReport(period_days=period_days)

    summary_row = (
        await db.execute(
            select(
                func.count().filter(
                    ScriptFlowTacticSearch.top_score >= RELEVANCE_HIGH_THRESHOLD
                ),
                func.count().filter(
                    (ScriptFlowTacticSearch.top_score < RELEVANCE_HIGH_THRESHOLD)
                    & (ScriptFlowTacticSearch.top_score > RELEVANCE_LOW_THRESHOLD)
                ),
                func.count().filter(
                    (ScriptFlowTacticSearch.top_score <= RELEVANCE_LOW_THRESHOLD)
                    & (ScriptFlowTacticSearch.hit_count > 0)
                ),
                func.count().filter(ScriptFlowTacticSearch.hit_count == 0),
                func.count(func.distinct(ScriptFlowTacticSearch.top_node_id)).filter(
                    ScriptFlowTacticSearch.top_score >= RELEVANCE_HIGH_THRESHOLD
                ),
            ).where(
                ScriptFlowTacticSearch.tenant_id == tenant_id,
                ScriptFlowTacticSearch.agent_id == agent_id,
                ScriptFlowTacticSearch.created_at >= since,
            )
        )
    ).one()

    summary = CoverageSummary(
        total_searches=int(total),
        relevant_count=int(summary_row[0] or 0),
        weak_count=int(summary_row[1] or 0),
        irrelevant_count=int(summary_row[2] or 0),
        no_match_count=int(summary_row[3] or 0),
        distinct_tactics_used=int(summary_row[4] or 0),
    )

    # Top tactics (relevant matches only) — with application/violation stats
    top_q = (
        select(
            ScriptFlowTacticSearch.top_node_id,
            ScriptFlowTacticSearch.top_title,
            func.count().label("hits"),
            func.avg(ScriptFlowTacticSearch.top_score).label("avg_score"),
            func.count().filter(ScriptFlowTacticSearch.applied.is_(True)).label("applied_n"),
            func.count().filter(ScriptFlowTacticSearch.violation.is_(True)).label("violation_n"),
            func.count().filter(ScriptFlowTacticSearch.followup_asked.is_(True)).label("followup_n"),
            func.count().filter(ScriptFlowTacticSearch.run_scored_at.is_not(None)).label("scored_n"),
        )
        .where(
            ScriptFlowTacticSearch.tenant_id == tenant_id,
            ScriptFlowTacticSearch.agent_id == agent_id,
            ScriptFlowTacticSearch.created_at >= since,
            ScriptFlowTacticSearch.top_node_id.is_not(None),
            ScriptFlowTacticSearch.top_score >= RELEVANCE_HIGH_THRESHOLD,
        )
        .group_by(
            ScriptFlowTacticSearch.top_node_id,
            ScriptFlowTacticSearch.top_title,
        )
        .order_by(desc("hits"))
        .limit(top_n_tactics)
    )
    top_rows = (await db.execute(top_q)).all()
    top_tactics = [
        TopTactic(
            node_id=str(r.top_node_id),
            title=r.top_title,
            hit_count=int(r.hits),
            avg_score=float(r.avg_score or 0.0),
            applied_count=int(r.applied_n or 0),
            violation_count=int(r.violation_n or 0),
            followup_count=int(r.followup_n or 0),
            scored_count=int(r.scored_n or 0),
        )
        for r in top_rows
    ]

    # Gap queries — weak/irrelevant matches, deduplicated by query text
    gap_q = (
        select(
            ScriptFlowTacticSearch.query,
            func.max(ScriptFlowTacticSearch.top_title).label("top_title"),
            func.max(ScriptFlowTacticSearch.top_score).label("top_score"),
            func.max(ScriptFlowTacticSearch.created_at).label("last_seen"),
            func.count().label("occurrences"),
        )
        .where(
            ScriptFlowTacticSearch.tenant_id == tenant_id,
            ScriptFlowTacticSearch.agent_id == agent_id,
            ScriptFlowTacticSearch.created_at >= since,
            ScriptFlowTacticSearch.hit_count > 0,
            ScriptFlowTacticSearch.top_score < RELEVANCE_HIGH_THRESHOLD,
        )
        .group_by(ScriptFlowTacticSearch.query)
        .order_by(desc("occurrences"), desc("last_seen"))
        .limit(top_n_gaps)
    )
    gap_rows = (await db.execute(gap_q)).all()
    gap_queries = [
        GapQuery(
            query=r.query,
            top_title=r.top_title,
            top_score=float(r.top_score) if r.top_score is not None else None,
            created_at=r.last_seen,
            occurrences=int(r.occurrences),
        )
        for r in gap_rows
    ]

    # No-match queries
    nomatch_q = (
        select(
            ScriptFlowTacticSearch.query,
            func.max(ScriptFlowTacticSearch.created_at).label("last_seen"),
            func.count().label("occurrences"),
        )
        .where(
            ScriptFlowTacticSearch.tenant_id == tenant_id,
            ScriptFlowTacticSearch.agent_id == agent_id,
            ScriptFlowTacticSearch.created_at >= since,
            ScriptFlowTacticSearch.hit_count == 0,
        )
        .group_by(ScriptFlowTacticSearch.query)
        .order_by(desc("occurrences"), desc("last_seen"))
        .limit(top_n_gaps)
    )
    nomatch_rows = (await db.execute(nomatch_q)).all()
    no_match_queries = [
        GapQuery(
            query=r.query,
            top_title=None,
            top_score=None,
            created_at=r.last_seen,
            occurrences=int(r.occurrences),
        )
        for r in nomatch_rows
    ]

    return CoverageReport(
        period_days=period_days,
        summary=summary,
        top_tactics=top_tactics,
        gap_queries=gap_queries,
        no_match_queries=no_match_queries,
    )


def coverage_report_to_dict(r: CoverageReport) -> dict[str, Any]:
    return {
        "period_days": r.period_days,
        "thresholds": {
            "relevant": RELEVANCE_HIGH_THRESHOLD,
            "irrelevant": RELEVANCE_LOW_THRESHOLD,
        },
        "summary": {
            "total_searches": r.summary.total_searches,
            "relevant_count": r.summary.relevant_count,
            "weak_count": r.summary.weak_count,
            "irrelevant_count": r.summary.irrelevant_count,
            "no_match_count": r.summary.no_match_count,
            "distinct_tactics_used": r.summary.distinct_tactics_used,
        },
        "top_tactics": [
            {
                "node_id": t.node_id,
                "title": t.title,
                "hit_count": t.hit_count,
                "avg_score": round(t.avg_score, 3),
                "scored_count": t.scored_count,
                "applied_count": t.applied_count,
                "violation_count": t.violation_count,
                "followup_count": t.followup_count,
                "applied_rate": (
                    round(t.applied_count / t.scored_count, 2)
                    if t.scored_count > 0 else None
                ),
            }
            for t in r.top_tactics
        ],
        "gap_queries": [
            {
                "query": g.query,
                "top_title": g.top_title,
                "top_score": round(g.top_score, 3) if g.top_score is not None else None,
                "occurrences": g.occurrences,
                "last_seen": g.created_at.isoformat() if g.created_at else None,
            }
            for g in r.gap_queries
        ],
        "no_match_queries": [
            {
                "query": g.query,
                "occurrences": g.occurrences,
                "last_seen": g.created_at.isoformat() if g.created_at else None,
            }
            for g in r.no_match_queries
        ],
    }
