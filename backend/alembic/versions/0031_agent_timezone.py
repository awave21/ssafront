"""add timezone field to agents

Revision ID: 0031_agent_timezone
Revises: 0030_tool_http_enhancements
Create Date: 2026-02-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0031_agent_timezone"
down_revision = "0030_tool_http_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
    )


def downgrade() -> None:
    op.drop_column("agents", "timezone")
