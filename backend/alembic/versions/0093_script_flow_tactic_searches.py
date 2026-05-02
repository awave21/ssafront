"""Log of search_expert_tactics calls for coverage analytics.

Revision ID: 0093
Revises: 0092
Create Date: 2026-05-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0093"
down_revision: Union[str, None] = "0092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "script_flow_tactic_searches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", sa.String(length=200), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("service_id", sa.String(length=120), nullable=True),
        sa.Column("top_node_id", sa.String(length=200), nullable=True),
        sa.Column("top_title", sa.String(length=255), nullable=True),
        sa.Column("top_score", sa.Float(), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "results",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("search_mode", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_script_flow_tactic_searches_tenant_agent_created",
        "script_flow_tactic_searches",
        ["tenant_id", "agent_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_script_flow_tactic_searches_top_node",
        "script_flow_tactic_searches",
        ["agent_id", "top_node_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_script_flow_tactic_searches_top_node", table_name="script_flow_tactic_searches")
    op.drop_index(
        "ix_script_flow_tactic_searches_tenant_agent_created",
        table_name="script_flow_tactic_searches",
    )
    op.drop_table("script_flow_tactic_searches")
