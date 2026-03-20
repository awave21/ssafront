"""add model name to run token usage steps

Revision ID: 0026_run_token_usage_model_name
Revises: 0025_system_prompt_versions
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0026_run_token_usage_model_name"
down_revision = "0025_system_prompt_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_token_usage_steps",
        sa.Column("model_name", sa.String(length=200), nullable=True),
    )
    op.create_index(
        "ix_run_token_usage_steps_model_name",
        "run_token_usage_steps",
        ["model_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_run_token_usage_steps_model_name", table_name="run_token_usage_steps")
    op.drop_column("run_token_usage_steps", "model_name")
