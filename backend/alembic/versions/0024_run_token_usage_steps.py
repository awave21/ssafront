"""add run token usage steps table

Revision ID: 0024_run_token_usage_steps
Revises: 0023_move_pause_to_agents
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0024_run_token_usage_steps"
down_revision = "0023_move_pause_to_agents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_token_usage_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id", sa.String(200), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_run_token_usage_steps_tenant_id", "run_token_usage_steps", ["tenant_id"])
    op.create_index("ix_run_token_usage_steps_agent_id", "run_token_usage_steps", ["agent_id"])
    op.create_index("ix_run_token_usage_steps_run_id", "run_token_usage_steps", ["run_id"])
    op.create_index("ix_run_token_usage_steps_session_id", "run_token_usage_steps", ["session_id"])
    op.create_index(
        "ix_run_token_usage_steps_run_step",
        "run_token_usage_steps",
        ["run_id", "step_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_run_token_usage_steps_run_step", table_name="run_token_usage_steps")
    op.drop_index("ix_run_token_usage_steps_session_id", table_name="run_token_usage_steps")
    op.drop_index("ix_run_token_usage_steps_run_id", table_name="run_token_usage_steps")
    op.drop_index("ix_run_token_usage_steps_agent_id", table_name="run_token_usage_steps")
    op.drop_index("ix_run_token_usage_steps_tenant_id", table_name="run_token_usage_steps")
    op.drop_table("run_token_usage_steps")
