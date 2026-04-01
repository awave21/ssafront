"""channels wappi max bot id

Revision ID: 0067
Revises: 0066
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("wappi_max_bot_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channels", "wappi_max_bot_id")
