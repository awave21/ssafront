"""Add per-user agent state table.

Revision ID: 0040
Revises: 0039
Create Date: 2026-03-07
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_user_states",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("platform_user_id", sa.String(length=200), nullable=False),
        sa.Column("is_disabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "platform", "platform_user_id", name="uq_agent_user_state_identity"),
    )
    op.create_index(op.f("ix_agent_user_states_agent_id"), "agent_user_states", ["agent_id"], unique=False)
    op.create_index(op.f("ix_agent_user_states_tenant_id"), "agent_user_states", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_user_states_tenant_id"), table_name="agent_user_states")
    op.drop_index(op.f("ix_agent_user_states_agent_id"), table_name="agent_user_states")
    op.drop_table("agent_user_states")
