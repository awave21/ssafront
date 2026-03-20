"""add sqns integration metadata to agents

Revision ID: 0009_agent_sqns_integration
Revises: 0008_session_messages
Create Date: 2026-01-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_agent_sqns_integration"
down_revision = "0008_session_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("sqns_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "agents",
        sa.Column("sqns_configured", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "agents",
        sa.Column("sqns_host", sa.String(200), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column(
            "sqns_credential_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("credentials.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "agents",
        sa.Column("sqns_status", sa.String(50), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("sqns_last_sync_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("sqns_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "sqns_error")
    op.drop_column("agents", "sqns_last_sync_at")
    op.drop_column("agents", "sqns_status")
    op.drop_column("agents", "sqns_credential_id")
    op.drop_column("agents", "sqns_host")
    op.drop_column("agents", "sqns_configured")
    op.drop_column("agents", "sqns_enabled")
