"""Harden agent analysis API contract

Revision ID: 0043
Revises: 0042
Create Date: 2026-03-15
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_analysis_jobs",
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "agent_analysis_jobs",
        sa.Column("cancelled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_agent_analysis_jobs_tenant_agent_idempotency_key",
        "agent_analysis_jobs",
        ["tenant_id", "agent_id", "idempotency_key"],
    )
    op.create_check_constraint(
        "ck_agent_analysis_jobs_status",
        "agent_analysis_jobs",
        "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_agent_analysis_jobs_stage",
        "agent_analysis_jobs",
        "stage IN ('queued', 'collecting', 'analyzing', 'persisting', 'done', 'failed', 'cancelled')",
    )

    op.add_column(
        "agent_analysis_recommendations",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_analysis_recommendations",
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_agent_analysis_recommendations_reviewed_by_user_id",
        "agent_analysis_recommendations",
        ["reviewed_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_analysis_recommendations_reviewed_by_user_id",
        table_name="agent_analysis_recommendations",
    )
    op.drop_column("agent_analysis_recommendations", "reviewed_by_user_id")
    op.drop_column("agent_analysis_recommendations", "reviewed_at")

    op.drop_constraint("ck_agent_analysis_jobs_stage", "agent_analysis_jobs", type_="check")
    op.drop_constraint("ck_agent_analysis_jobs_status", "agent_analysis_jobs", type_="check")
    op.drop_constraint(
        "uq_agent_analysis_jobs_tenant_agent_idempotency_key",
        "agent_analysis_jobs",
        type_="unique",
    )
    op.drop_column("agent_analysis_jobs", "cancelled_by_user_id")
    op.drop_column("agent_analysis_jobs", "created_by_user_id")
