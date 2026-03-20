"""add sqns_warning to agents

Revision ID: 0013_agent_sqns_warning
Revises: 0012_sqns_services_cache
Create Date: 2026-01-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_agent_sqns_warning"
down_revision = "0012_sqns_services_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sqns_warning column to agents table
    op.execute(
        """
        ALTER TABLE agents 
        ADD COLUMN IF NOT EXISTS sqns_warning TEXT;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS sqns_warning;")
