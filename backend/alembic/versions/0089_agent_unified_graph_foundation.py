"""Agent-level unified graph storage (SQNS + knowledge structure + future LLM edges).

Revision ID: 0089
Revises: 0088
Create Date: 2026-04-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0089"
down_revision: Union[str, None] = "0088"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_unified_graph_nodes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("origin_slice", sa.String(length=32), nullable=False),
        sa.Column("graph_node_id", sa.String(length=255), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domain_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("provenance_tier", sa.String(length=16), nullable=False, server_default="gold"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_unified_graph_nodes_tenant_id", "agent_unified_graph_nodes", ["tenant_id"])
    op.create_index("ix_agent_unified_graph_nodes_agent_id", "agent_unified_graph_nodes", ["agent_id"])
    op.create_index("ix_agent_unified_graph_nodes_origin_slice", "agent_unified_graph_nodes", ["origin_slice"])
    op.create_index("ix_agent_unified_graph_nodes_graph_node_id", "agent_unified_graph_nodes", ["graph_node_id"])
    op.create_index("ix_agent_unified_graph_nodes_entity_type", "agent_unified_graph_nodes", ["entity_type"])
    op.create_index("ix_agent_unified_graph_nodes_domain_entity_id", "agent_unified_graph_nodes", ["domain_entity_id"])
    op.create_index(
        "ix_agent_unified_graph_nodes_agent_origin_entity",
        "agent_unified_graph_nodes",
        ["agent_id", "origin_slice", "entity_type"],
    )
    op.create_index(
        "uq_agent_unified_graph_nodes_agent_graph_node_id",
        "agent_unified_graph_nodes",
        ["agent_id", "graph_node_id"],
        unique=True,
    )

    op.create_table(
        "agent_unified_graph_relations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("origin_slice", sa.String(length=32), nullable=False),
        sa.Column("source_graph_node_id", sa.String(length=255), nullable=False),
        sa.Column("target_graph_node_id", sa.String(length=255), nullable=False),
        sa.Column("relation_type", sa.String(length=80), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("provenance_tier", sa.String(length=16), nullable=False, server_default="gold"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_unified_graph_relations_tenant_id", "agent_unified_graph_relations", ["tenant_id"])
    op.create_index("ix_agent_unified_graph_relations_agent_id", "agent_unified_graph_relations", ["agent_id"])
    op.create_index(
        "ix_agent_unified_graph_relations_origin_slice",
        "agent_unified_graph_relations",
        ["origin_slice"],
    )
    op.create_index(
        "ix_agent_unified_graph_relations_source_graph_node_id",
        "agent_unified_graph_relations",
        ["source_graph_node_id"],
    )
    op.create_index(
        "ix_agent_unified_graph_relations_target_graph_node_id",
        "agent_unified_graph_relations",
        ["target_graph_node_id"],
    )
    op.create_index(
        "ix_agent_unified_graph_relations_relation_type",
        "agent_unified_graph_relations",
        ["relation_type"],
    )
    op.create_index(
        "ix_agent_unified_graph_relations_agent_source",
        "agent_unified_graph_relations",
        ["agent_id", "source_graph_node_id"],
    )
    op.create_index(
        "ix_agent_unified_graph_relations_agent_target",
        "agent_unified_graph_relations",
        ["agent_id", "target_graph_node_id"],
    )


def downgrade() -> None:
    op.drop_table("agent_unified_graph_relations")
    op.drop_table("agent_unified_graph_nodes")
