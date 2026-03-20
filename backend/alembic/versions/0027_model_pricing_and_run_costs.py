"""add model pricing and run costs

Revision ID: 0027_model_pricing_and_run_costs
Revises: 0026_run_token_usage_model_name
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0027_model_pricing_and_run_costs"
down_revision = "0026_run_token_usage_model_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_pricing",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("input_usd", sa.Numeric(18, 8), nullable=False),
        sa.Column("output_usd", sa.Numeric(18, 8), nullable=False),
        sa.Column("cached_input_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("reasoning_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("input_rub", sa.Numeric(18, 8), nullable=False),
        sa.Column("output_rub", sa.Numeric(18, 8), nullable=False),
        sa.Column("cached_input_rub", sa.Numeric(18, 8), nullable=True),
        sa.Column("reasoning_rub", sa.Numeric(18, 8), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_model_pricing_provider", "model_pricing", ["provider"])
    op.create_index("ix_model_pricing_model_name", "model_pricing", ["model_name"])
    op.create_unique_constraint(
        "uq_model_pricing_provider_model_name",
        "model_pricing",
        ["provider", "model_name"],
    )

    op.add_column(
        "runs",
        sa.Column("cost_currency", sa.String(length=3), nullable=False, server_default="USD"),
    )
    op.add_column("runs", sa.Column("cost_usd", sa.Numeric(18, 10), nullable=True))
    op.add_column("runs", sa.Column("cost_rub", sa.Numeric(18, 10), nullable=True))
    op.add_column("runs", sa.Column("cost_usd_logfire", sa.Numeric(18, 10), nullable=True))
    op.add_column(
        "runs",
        sa.Column(
            "logfire_reconcile_status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "runs",
        sa.Column(
            "logfire_reconcile_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("runs", sa.Column("logfire_reconcile_error", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("logfire_reconciled_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.create_index("ix_runs_logfire_reconcile_status", "runs", ["logfire_reconcile_status"])

    op.add_column("run_token_usage_steps", sa.Column("input_cached_tokens", sa.Integer(), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("input_non_cached_tokens", sa.Integer(), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("cost_usd", sa.Numeric(18, 10), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("cost_rub", sa.Numeric(18, 10), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("cost_usd_logfire", sa.Numeric(18, 10), nullable=True))


def downgrade() -> None:
    op.drop_column("run_token_usage_steps", "cost_usd_logfire")
    op.drop_column("run_token_usage_steps", "cost_rub")
    op.drop_column("run_token_usage_steps", "cost_usd")
    op.drop_column("run_token_usage_steps", "input_non_cached_tokens")
    op.drop_column("run_token_usage_steps", "input_cached_tokens")

    op.drop_index("ix_runs_logfire_reconcile_status", table_name="runs")
    op.drop_column("runs", "logfire_reconciled_at")
    op.drop_column("runs", "logfire_reconcile_error")
    op.drop_column("runs", "logfire_reconcile_attempts")
    op.drop_column("runs", "logfire_reconcile_status")
    op.drop_column("runs", "cost_usd_logfire")
    op.drop_column("runs", "cost_rub")
    op.drop_column("runs", "cost_usd")
    op.drop_column("runs", "cost_currency")

    op.drop_constraint("uq_model_pricing_provider_model_name", "model_pricing", type_="unique")
    op.drop_index("ix_model_pricing_model_name", table_name="model_pricing")
    op.drop_index("ix_model_pricing_provider", table_name="model_pricing")
    op.drop_table("model_pricing")
