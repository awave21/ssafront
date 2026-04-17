"""script_nodes_expertise

Revision ID: 0072
Revises: 0071
Create Date: 2026-04-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector extension must already exist (created in earlier migrations)
    op.create_table(
        "script_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_ref_id", sa.String(200), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False, server_default="expertise"),
        sa.Column("stage", sa.String(100), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("service_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("employee_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("situation", sa.Text(), nullable=False, server_default="''"),
        sa.Column("why_it_works", sa.Text(), nullable=True),
        sa.Column("approach", sa.Text(), nullable=True),
        sa.Column("example_phrases", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("watch_out", sa.Text(), nullable=True),
        sa.Column("good_question", sa.Text(), nullable=True),
        sa.Column("next_steps", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_entry_point", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("embedding", sa.Text(), nullable=True),  # placeholder, replaced below
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["flow_id"], ["script_flows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Replace text placeholder with proper vector column
    op.drop_column("script_nodes", "embedding")
    op.execute("ALTER TABLE script_nodes ADD COLUMN embedding vector(1536)")

    op.create_index("ix_script_nodes_flow_id", "script_nodes", ["flow_id"])
    op.create_index("ix_script_nodes_agent_id", "script_nodes", ["agent_id"])
    op.create_index("ix_script_nodes_tenant_id", "script_nodes", ["tenant_id"])
    op.create_index(
        "ix_script_nodes_embedding_hnsw",
        "script_nodes",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "session_script_contexts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topics_discussed", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("objection_attempts", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("detected_service_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detected_employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_session_script_contexts_session_id"),
    )
    op.create_index("ix_session_script_contexts_agent_id", "session_script_contexts", ["agent_id"])
    op.create_index("ix_session_script_contexts_tenant_id", "session_script_contexts", ["tenant_id"])
    op.create_index("ix_session_script_contexts_session_id", "session_script_contexts", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_session_script_contexts_session_id", "session_script_contexts")
    op.drop_index("ix_session_script_contexts_tenant_id", "session_script_contexts")
    op.drop_index("ix_session_script_contexts_agent_id", "session_script_contexts")
    op.drop_table("session_script_contexts")

    op.drop_index("ix_script_nodes_embedding_hnsw", "script_nodes")
    op.drop_index("ix_script_nodes_tenant_id", "script_nodes")
    op.drop_index("ix_script_nodes_agent_id", "script_nodes")
    op.drop_index("ix_script_nodes_flow_id", "script_nodes")
    op.drop_table("script_nodes")
