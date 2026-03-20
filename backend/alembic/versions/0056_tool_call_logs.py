"""tool call logs analytics history

Revision ID: 0056
Revises: 0055
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_call_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("tool_description", sa.Text(), nullable=True),
        sa.Column("tool_settings_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("invoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("user_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_call_logs_tenant_id", "tool_call_logs", ["tenant_id"], unique=False)
    op.create_index("ix_tool_call_logs_run_id", "tool_call_logs", ["run_id"], unique=False)
    op.create_index("ix_tool_call_logs_agent_id", "tool_call_logs", ["agent_id"], unique=False)
    op.create_index("ix_tool_call_logs_tool_id", "tool_call_logs", ["tool_id"], unique=False)
    op.create_index("ix_tool_call_logs_tool_name", "tool_call_logs", ["tool_name"], unique=False)
    op.create_index("ix_tool_call_logs_status", "tool_call_logs", ["status"], unique=False)
    op.create_index("ix_tool_call_logs_invoked_at", "tool_call_logs", ["invoked_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tool_call_logs_invoked_at", table_name="tool_call_logs")
    op.drop_index("ix_tool_call_logs_status", table_name="tool_call_logs")
    op.drop_index("ix_tool_call_logs_tool_name", table_name="tool_call_logs")
    op.drop_index("ix_tool_call_logs_tool_id", table_name="tool_call_logs")
    op.drop_index("ix_tool_call_logs_agent_id", table_name="tool_call_logs")
    op.drop_index("ix_tool_call_logs_run_id", table_name="tool_call_logs")
    op.drop_index("ix_tool_call_logs_tenant_id", table_name="tool_call_logs")
    op.drop_table("tool_call_logs")
