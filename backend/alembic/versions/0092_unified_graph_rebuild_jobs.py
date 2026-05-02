"""Persisted rebuild jobs for Microsoft GraphRAG unified graph.

Revision ID: 0092
Revises: 0091
Create Date: 2026-04-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0092"
down_revision: Union[str, None] = "0091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unified_graph_rebuild_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("stage", sa.String(length=50), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("active_sqns_only", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_unified_graph_rebuild_jobs_status",
        ),
        sa.CheckConstraint(
            "progress_pct >= 0 AND progress_pct <= 100",
            name="ck_unified_graph_rebuild_jobs_progress_pct",
        ),
    )
    op.create_index(
        "ix_unified_graph_rebuild_jobs_tenant_id",
        "unified_graph_rebuild_jobs",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_unified_graph_rebuild_jobs_agent_id",
        "unified_graph_rebuild_jobs",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_unified_graph_rebuild_jobs_tenant_agent_created_at",
        "unified_graph_rebuild_jobs",
        ["tenant_id", "agent_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_unified_graph_rebuild_jobs_tenant_agent_status",
        "unified_graph_rebuild_jobs",
        ["tenant_id", "agent_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_unified_graph_rebuild_jobs_tenant_agent_status",
        table_name="unified_graph_rebuild_jobs",
    )
    op.drop_index(
        "ix_unified_graph_rebuild_jobs_tenant_agent_created_at",
        table_name="unified_graph_rebuild_jobs",
    )
    op.drop_index("ix_unified_graph_rebuild_jobs_agent_id", table_name="unified_graph_rebuild_jobs")
    op.drop_index("ix_unified_graph_rebuild_jobs_tenant_id", table_name="unified_graph_rebuild_jobs")
    op.drop_table("unified_graph_rebuild_jobs")
