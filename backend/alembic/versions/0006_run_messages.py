"""add messages to runs

Revision ID: 0006_run_messages
Revises: 0005_credentials
Create Date: 2026-01-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_run_messages"
down_revision = "0005_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "messages")
