"""Add agent analysis jobs, reports and recommendations tables

Revision ID: 0042
Revises: 0041
Create Date: 2026-03-15
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(length=50), nullable=False, server_default="queued"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_hours", sa.Integer(), nullable=False),
        sa.Column("only_with_manager", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_dialogs", sa.Integer(), nullable=False),
        sa.Column("history_limit", sa.Integer(), nullable=False),
        sa.Column("max_tokens_per_job", sa.Integer(), nullable=False),
        sa.Column("max_llm_requests_per_job", sa.Integer(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_requests_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("meta_model", sa.String(length=200), nullable=True),
        sa.Column("analysis_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("progress_pct >= 0 AND progress_pct <= 100", name="ck_agent_analysis_jobs_progress_pct"),
        sa.CheckConstraint("window_hours >= 24 AND window_hours <= 168", name="ck_agent_analysis_jobs_window_hours"),
    )
    op.create_index("ix_agent_analysis_jobs_tenant_id", "agent_analysis_jobs", ["tenant_id"])
    op.create_index("ix_agent_analysis_jobs_agent_id", "agent_analysis_jobs", ["agent_id"])
    op.create_index(
        "ix_agent_analysis_jobs_tenant_agent_created_at",
        "agent_analysis_jobs",
        ["tenant_id", "agent_id", "created_at"],
    )
    op.create_index(
        "ix_agent_analysis_jobs_tenant_agent_status",
        "agent_analysis_jobs",
        ["tenant_id", "agent_id", "status"],
    )

    op.create_table(
        "agent_analysis_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_hours", sa.Integer(), nullable=False),
        sa.Column("analysis_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analyzer_version", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("kpis", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "top_failure_topics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "recommendation_count_by_category",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("raw_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("window_hours >= 24 AND window_hours <= 168", name="ck_agent_analysis_reports_window_hours"),
    )
    op.create_index("ix_agent_analysis_reports_tenant_id", "agent_analysis_reports", ["tenant_id"])
    op.create_index("ix_agent_analysis_reports_agent_id", "agent_analysis_reports", ["agent_id"])
    op.create_index("ix_agent_analysis_reports_job_id", "agent_analysis_reports", ["job_id"])
    op.create_unique_constraint("uq_agent_analysis_reports_job_id", "agent_analysis_reports", ["job_id"])

    op.create_table(
        "agent_analysis_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_analysis_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=True),
        sa.Column(
            "evidence_dialog_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("reviewer_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_agent_analysis_recommendations_confidence"),
    )
    op.create_index("ix_agent_analysis_recommendations_tenant_id", "agent_analysis_recommendations", ["tenant_id"])
    op.create_index("ix_agent_analysis_recommendations_agent_id", "agent_analysis_recommendations", ["agent_id"])
    op.create_index("ix_agent_analysis_recommendations_job_id", "agent_analysis_recommendations", ["job_id"])
    op.create_index("ix_agent_analysis_recommendations_report_id", "agent_analysis_recommendations", ["report_id"])
    op.create_index(
        "ix_agent_analysis_recommendations_tenant_agent_status",
        "agent_analysis_recommendations",
        ["tenant_id", "agent_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_analysis_recommendations_tenant_agent_status",
        table_name="agent_analysis_recommendations",
    )
    op.drop_index("ix_agent_analysis_recommendations_report_id", table_name="agent_analysis_recommendations")
    op.drop_index("ix_agent_analysis_recommendations_job_id", table_name="agent_analysis_recommendations")
    op.drop_index("ix_agent_analysis_recommendations_agent_id", table_name="agent_analysis_recommendations")
    op.drop_index("ix_agent_analysis_recommendations_tenant_id", table_name="agent_analysis_recommendations")
    op.drop_table("agent_analysis_recommendations")

    op.drop_constraint("uq_agent_analysis_reports_job_id", "agent_analysis_reports", type_="unique")
    op.drop_index("ix_agent_analysis_reports_job_id", table_name="agent_analysis_reports")
    op.drop_index("ix_agent_analysis_reports_agent_id", table_name="agent_analysis_reports")
    op.drop_index("ix_agent_analysis_reports_tenant_id", table_name="agent_analysis_reports")
    op.drop_table("agent_analysis_reports")

    op.drop_index("ix_agent_analysis_jobs_tenant_agent_status", table_name="agent_analysis_jobs")
    op.drop_index("ix_agent_analysis_jobs_tenant_agent_created_at", table_name="agent_analysis_jobs")
    op.drop_index("ix_agent_analysis_jobs_agent_id", table_name="agent_analysis_jobs")
    op.drop_index("ix_agent_analysis_jobs_tenant_id", table_name="agent_analysis_jobs")
    op.drop_table("agent_analysis_jobs")
