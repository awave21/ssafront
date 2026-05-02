"""Stage 3-5: tactic application scoring + gap clustering + missed-call detector.

Revision ID: 0094
Revises: 0093
Create Date: 2026-05-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0094"
down_revision: Union[str, None] = "0093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Stage 3: extra columns on the existing search log ---
    op.add_column(
        "script_flow_tactic_searches",
        sa.Column("run_scored_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "script_flow_tactic_searches",
        sa.Column("applied", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "script_flow_tactic_searches",
        sa.Column("violation", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "script_flow_tactic_searches",
        sa.Column("followup_asked", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "script_flow_tactic_searches",
        sa.Column("agent_response_excerpt", sa.Text(), nullable=True),
    )

    # --- Stage 4: gap clusters table ---
    op.create_table(
        "script_flow_coverage_gap_clusters",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=False, server_default=sa.text("7")),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("query_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_score", sa.Float(), nullable=True),
        sa.Column(
            "sample_queries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_script_flow_coverage_gap_clusters_tenant_agent_created",
        "script_flow_coverage_gap_clusters",
        ["tenant_id", "agent_id", "created_at"],
        unique=False,
    )

    # --- Stage 5: missed tactic calls table ---
    op.create_table(
        "script_flow_missed_tactic_calls",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_script_flow_missed_tactic_calls_tenant_agent_created",
        "script_flow_missed_tactic_calls",
        ["tenant_id", "agent_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_script_flow_missed_tactic_calls_classification",
        "script_flow_missed_tactic_calls",
        ["agent_id", "classification"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_script_flow_missed_tactic_calls_classification",
        table_name="script_flow_missed_tactic_calls",
    )
    op.drop_index(
        "ix_script_flow_missed_tactic_calls_tenant_agent_created",
        table_name="script_flow_missed_tactic_calls",
    )
    op.drop_table("script_flow_missed_tactic_calls")

    op.drop_index(
        "ix_script_flow_coverage_gap_clusters_tenant_agent_created",
        table_name="script_flow_coverage_gap_clusters",
    )
    op.drop_table("script_flow_coverage_gap_clusters")

    op.drop_column("script_flow_tactic_searches", "agent_response_excerpt")
    op.drop_column("script_flow_tactic_searches", "followup_asked")
    op.drop_column("script_flow_tactic_searches", "violation")
    op.drop_column("script_flow_tactic_searches", "applied")
    op.drop_column("script_flow_tactic_searches", "run_scored_at")
