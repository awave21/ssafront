"""add current_node_ref_id to session_script_contexts

Revision ID: 0073
Revises: 0072
Create Date: 2026-04-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "session_script_contexts",
        sa.Column("current_node_ref_id", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("session_script_contexts", "current_node_ref_id")
