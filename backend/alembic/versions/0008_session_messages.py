"""create session_messages table

Revision ID: 0008_session_messages
Revises: 0007_agent_memory_limit
Create Date: 2026-01-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_session_messages"
down_revision = "0007_agent_memory_limit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(200), nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_index", sa.Integer(), nullable=False),
        sa.Column(
            "message",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index(
        "ix_session_messages_session_index",
        "session_messages",
        ["session_id", "message_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_session_messages_session_index", table_name="session_messages")
    op.drop_table("session_messages")
