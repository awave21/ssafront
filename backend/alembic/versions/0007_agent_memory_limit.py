"""add max_history_messages to agents

Revision ID: 0007_agent_memory_limit
Revises: 0006_run_messages
Create Date: 2026-01-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_agent_memory_limit"
down_revision = "0006_run_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("max_history_messages", sa.Integer(), server_default="10", nullable=False))


def downgrade() -> None:
    op.drop_column("agents", "max_history_messages")
