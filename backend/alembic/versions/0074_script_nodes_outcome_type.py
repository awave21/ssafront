"""add outcome_type and final_action to script_nodes

Revision ID: 0074
Revises: 0073
Create Date: 2026-04-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "script_nodes",
        sa.Column("outcome_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "script_nodes",
        sa.Column("final_action", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("script_nodes", "outcome_type")
    op.drop_column("script_nodes", "final_action")
