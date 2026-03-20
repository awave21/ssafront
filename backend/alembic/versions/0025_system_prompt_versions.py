"""add system_prompt_versions table

Revision ID: 0025_system_prompt_versions
Revises: 0024_run_token_usage_steps
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0025_system_prompt_versions"
down_revision = "0024_run_token_usage_steps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("change_summary", sa.String(500), nullable=True),
        sa.Column("triggered_by", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_spv_agent_id", "system_prompt_versions", ["agent_id"])
    op.create_index("ix_spv_tenant_id", "system_prompt_versions", ["tenant_id"])
    op.create_index("ix_spv_agent_active", "system_prompt_versions", ["agent_id", "is_active"])
    op.create_index(
        "ix_spv_agent_version",
        "system_prompt_versions",
        ["agent_id", "version_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_spv_agent_version", table_name="system_prompt_versions")
    op.drop_index("ix_spv_agent_active", table_name="system_prompt_versions")
    op.drop_index("ix_spv_tenant_id", table_name="system_prompt_versions")
    op.drop_index("ix_spv_agent_id", table_name="system_prompt_versions")
    op.drop_table("system_prompt_versions")
