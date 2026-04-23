"""Add ScriptFlow GraphRAG diagnostics table.

Revision ID: 0088
Revises: 0087
Create Date: 2026-04-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0088"
down_revision: Union[str, None] = "0087"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "script_flow_graph_diagnostics",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "flow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("script_flows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("flow_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extraction_model", sa.String(length=120), nullable=True),
        sa.Column("summary_model", sa.String(length=120), nullable=True),
        sa.Column("extraction_mode", sa.String(length=60), nullable=True),
        sa.Column("llm_ok_nodes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_failed_nodes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entity_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("community_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_llm_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_fallback_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("debug", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_script_flow_graph_diagnostics_tenant_id", "script_flow_graph_diagnostics", ["tenant_id"])
    op.create_index("ix_script_flow_graph_diagnostics_agent_id", "script_flow_graph_diagnostics", ["agent_id"])
    op.create_index("ix_script_flow_graph_diagnostics_flow_id", "script_flow_graph_diagnostics", ["flow_id"])
    op.create_index(
        "ix_script_flow_graph_diagnostics_flow_version_unique",
        "script_flow_graph_diagnostics",
        ["flow_id", "flow_version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_script_flow_graph_diagnostics_flow_version_unique", table_name="script_flow_graph_diagnostics")
    op.drop_index("ix_script_flow_graph_diagnostics_flow_id", table_name="script_flow_graph_diagnostics")
    op.drop_index("ix_script_flow_graph_diagnostics_agent_id", table_name="script_flow_graph_diagnostics")
    op.drop_index("ix_script_flow_graph_diagnostics_tenant_id", table_name="script_flow_graph_diagnostics")
    op.drop_table("script_flow_graph_diagnostics")

