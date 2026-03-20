"""add token usage and tools called fields to runs

Revision ID: 0010_run_token_usage
Revises: 0009_agent_sqns_integration
Create Date: 2026-01-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_run_token_usage"
down_revision = "0009_agent_sqns_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "runs",
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "runs",
        sa.Column("total_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "runs",
        sa.Column("tools_called", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("runs", "tools_called")
    op.drop_column("runs", "total_tokens")
    op.drop_column("runs", "completion_tokens")
    op.drop_column("runs", "prompt_tokens")
