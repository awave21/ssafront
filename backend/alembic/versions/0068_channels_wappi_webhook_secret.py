"""channels wappi webhook secret

Revision ID: 0068
Revises: 0067
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("wappi_webhook_secret", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channels", "wappi_webhook_secret")
