"""directory prompt_usage_snippet for system prompt copy-paste

Revision ID: 0061
Revises: 0060
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "directories",
        sa.Column("prompt_usage_snippet", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("directories", "prompt_usage_snippet")
