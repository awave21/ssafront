"""Add script flow node/edge retrieval index tables.

Revision ID: 0086
Revises: 0085
Create Date: 2026-04-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0086"
down_revision: Union[str, None] = "0085"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "script_flow_node_indexes",
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
        sa.Column("node_id", sa.String(length=120), nullable=False),
        sa.Column("node_type", sa.String(length=50), nullable=False),
        sa.Column("stage", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("service_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("employee_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("motive_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("objection_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("proof_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("constraint_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("required_followup_question", sa.Text(), nullable=True),
        sa.Column("communication_style", sa.String(length=100), nullable=True),
        sa.Column("preferred_phrases", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("forbidden_phrases", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("is_searchable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.execute("ALTER TABLE script_flow_node_indexes ADD COLUMN embedding vector(1536)")

    op.create_index("ix_script_flow_node_indexes_tenant_id", "script_flow_node_indexes", ["tenant_id"])
    op.create_index("ix_script_flow_node_indexes_agent_id", "script_flow_node_indexes", ["agent_id"])
    op.create_index("ix_script_flow_node_indexes_flow_id", "script_flow_node_indexes", ["flow_id"])
    op.create_index("ix_script_flow_node_indexes_node_id", "script_flow_node_indexes", ["node_id"])
    op.create_index("ix_script_flow_node_indexes_node_type", "script_flow_node_indexes", ["node_type"])
    op.create_index("ix_script_flow_node_indexes_stage", "script_flow_node_indexes", ["stage"])
    op.create_index(
        "ix_script_flow_node_indexes_flow_node_unique",
        "script_flow_node_indexes",
        ["flow_id", "node_id"],
        unique=True,
    )
    op.execute(
        "CREATE INDEX ix_script_flow_node_indexes_embedding_hnsw "
        "ON script_flow_node_indexes USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "script_flow_edge_indexes",
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
        sa.Column("source_node_id", sa.String(length=120), nullable=False),
        sa.Column("target_node_id", sa.String(length=120), nullable=False),
        sa.Column("source_handle", sa.String(length=120), nullable=True),
        sa.Column("branch_label", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_script_flow_edge_indexes_tenant_id", "script_flow_edge_indexes", ["tenant_id"])
    op.create_index("ix_script_flow_edge_indexes_agent_id", "script_flow_edge_indexes", ["agent_id"])
    op.create_index("ix_script_flow_edge_indexes_flow_id", "script_flow_edge_indexes", ["flow_id"])
    op.create_index("ix_script_flow_edge_indexes_source_node_id", "script_flow_edge_indexes", ["source_node_id"])
    op.create_index("ix_script_flow_edge_indexes_target_node_id", "script_flow_edge_indexes", ["target_node_id"])


def downgrade() -> None:
    op.drop_index("ix_script_flow_edge_indexes_target_node_id", table_name="script_flow_edge_indexes")
    op.drop_index("ix_script_flow_edge_indexes_source_node_id", table_name="script_flow_edge_indexes")
    op.drop_index("ix_script_flow_edge_indexes_flow_id", table_name="script_flow_edge_indexes")
    op.drop_index("ix_script_flow_edge_indexes_agent_id", table_name="script_flow_edge_indexes")
    op.drop_index("ix_script_flow_edge_indexes_tenant_id", table_name="script_flow_edge_indexes")
    op.drop_table("script_flow_edge_indexes")

    op.execute("DROP INDEX IF EXISTS ix_script_flow_node_indexes_embedding_hnsw")
    op.drop_index("ix_script_flow_node_indexes_flow_node_unique", table_name="script_flow_node_indexes")
    op.drop_index("ix_script_flow_node_indexes_stage", table_name="script_flow_node_indexes")
    op.drop_index("ix_script_flow_node_indexes_node_type", table_name="script_flow_node_indexes")
    op.drop_index("ix_script_flow_node_indexes_node_id", table_name="script_flow_node_indexes")
    op.drop_index("ix_script_flow_node_indexes_flow_id", table_name="script_flow_node_indexes")
    op.drop_index("ix_script_flow_node_indexes_agent_id", table_name="script_flow_node_indexes")
    op.drop_index("ix_script_flow_node_indexes_tenant_id", table_name="script_flow_node_indexes")
    op.drop_table("script_flow_node_indexes")
