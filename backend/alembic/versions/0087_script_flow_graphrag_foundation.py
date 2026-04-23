"""Add ScriptFlow GraphRAG storage tables.

Revision ID: 0087
Revises: 0086
Create Date: 2026-04-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0087"
down_revision: Union[str, None] = "0086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "script_flow_graph_nodes",
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
        sa.Column("graph_node_id", sa.String(length=255), nullable=False),
        sa.Column("node_kind", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_node_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("community_key", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_script_flow_graph_nodes_tenant_id", "script_flow_graph_nodes", ["tenant_id"])
    op.create_index("ix_script_flow_graph_nodes_agent_id", "script_flow_graph_nodes", ["agent_id"])
    op.create_index("ix_script_flow_graph_nodes_flow_id", "script_flow_graph_nodes", ["flow_id"])
    op.create_index("ix_script_flow_graph_nodes_graph_node_id", "script_flow_graph_nodes", ["graph_node_id"])
    op.create_index("ix_script_flow_graph_nodes_node_kind", "script_flow_graph_nodes", ["node_kind"])
    op.create_index("ix_script_flow_graph_nodes_entity_type", "script_flow_graph_nodes", ["entity_type"])
    op.create_index("ix_script_flow_graph_nodes_community_key", "script_flow_graph_nodes", ["community_key"])
    op.create_index(
        "ix_script_flow_graph_nodes_flow_graph_node_unique",
        "script_flow_graph_nodes",
        ["flow_id", "graph_node_id"],
        unique=True,
    )

    op.create_table(
        "script_flow_graph_relations",
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
        sa.Column("source_graph_node_id", sa.String(length=255), nullable=False),
        sa.Column("target_graph_node_id", sa.String(length=255), nullable=False),
        sa.Column("relation_type", sa.String(length=80), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_script_flow_graph_relations_tenant_id", "script_flow_graph_relations", ["tenant_id"])
    op.create_index("ix_script_flow_graph_relations_agent_id", "script_flow_graph_relations", ["agent_id"])
    op.create_index("ix_script_flow_graph_relations_flow_id", "script_flow_graph_relations", ["flow_id"])
    op.create_index("ix_script_flow_graph_relations_source_graph_node_id", "script_flow_graph_relations", ["source_graph_node_id"])
    op.create_index("ix_script_flow_graph_relations_target_graph_node_id", "script_flow_graph_relations", ["target_graph_node_id"])
    op.create_index("ix_script_flow_graph_relations_relation_type", "script_flow_graph_relations", ["relation_type"])

    op.create_table(
        "script_flow_graph_communities",
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
        sa.Column("community_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("node_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_script_flow_graph_communities_tenant_id", "script_flow_graph_communities", ["tenant_id"])
    op.create_index("ix_script_flow_graph_communities_agent_id", "script_flow_graph_communities", ["agent_id"])
    op.create_index("ix_script_flow_graph_communities_flow_id", "script_flow_graph_communities", ["flow_id"])
    op.create_index("ix_script_flow_graph_communities_community_key", "script_flow_graph_communities", ["community_key"])
    op.create_index(
        "ix_script_flow_graph_communities_flow_community_unique",
        "script_flow_graph_communities",
        ["flow_id", "community_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_script_flow_graph_communities_flow_community_unique", table_name="script_flow_graph_communities")
    op.drop_index("ix_script_flow_graph_communities_community_key", table_name="script_flow_graph_communities")
    op.drop_index("ix_script_flow_graph_communities_flow_id", table_name="script_flow_graph_communities")
    op.drop_index("ix_script_flow_graph_communities_agent_id", table_name="script_flow_graph_communities")
    op.drop_index("ix_script_flow_graph_communities_tenant_id", table_name="script_flow_graph_communities")
    op.drop_table("script_flow_graph_communities")

    op.drop_index("ix_script_flow_graph_relations_relation_type", table_name="script_flow_graph_relations")
    op.drop_index("ix_script_flow_graph_relations_target_graph_node_id", table_name="script_flow_graph_relations")
    op.drop_index("ix_script_flow_graph_relations_source_graph_node_id", table_name="script_flow_graph_relations")
    op.drop_index("ix_script_flow_graph_relations_flow_id", table_name="script_flow_graph_relations")
    op.drop_index("ix_script_flow_graph_relations_agent_id", table_name="script_flow_graph_relations")
    op.drop_index("ix_script_flow_graph_relations_tenant_id", table_name="script_flow_graph_relations")
    op.drop_table("script_flow_graph_relations")

    op.drop_index("ix_script_flow_graph_nodes_flow_graph_node_unique", table_name="script_flow_graph_nodes")
    op.drop_index("ix_script_flow_graph_nodes_community_key", table_name="script_flow_graph_nodes")
    op.drop_index("ix_script_flow_graph_nodes_entity_type", table_name="script_flow_graph_nodes")
    op.drop_index("ix_script_flow_graph_nodes_node_kind", table_name="script_flow_graph_nodes")
    op.drop_index("ix_script_flow_graph_nodes_graph_node_id", table_name="script_flow_graph_nodes")
    op.drop_index("ix_script_flow_graph_nodes_flow_id", table_name="script_flow_graph_nodes")
    op.drop_index("ix_script_flow_graph_nodes_agent_id", table_name="script_flow_graph_nodes")
    op.drop_index("ix_script_flow_graph_nodes_tenant_id", table_name="script_flow_graph_nodes")
    op.drop_table("script_flow_graph_nodes")
