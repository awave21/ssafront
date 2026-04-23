"""Expert script flows (Vue Flow JSON + retrieval index pipeline).

Revision ID: 0071
Revises: 0070
Create Date: 2026-04-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0071"
down_revision: Union[str, None] = "0070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE script_flow_status AS ENUM ('draft', 'published');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE script_flow_index_status AS ENUM ('idle', 'pending', 'indexing', 'indexed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.create_table(
        "script_flows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column(
            "flow_status",
            postgresql.ENUM("draft", "published", name="script_flow_status", create_type=False),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("published_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("indexed_version", sa.Integer(), nullable=True),
        sa.Column(
            "flow_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "flow_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("compiled_text", sa.Text(), nullable=True),
        sa.Column(
            "index_status",
            postgresql.ENUM(
                "idle",
                "pending",
                "indexing",
                "indexed",
                "failed",
                name="script_flow_index_status",
                create_type=False,
            ),
            server_default="idle",
            nullable=False,
        ),
        sa.Column("index_error", sa.Text(), nullable=True),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_script_flows_tenant_id", "script_flows", ["tenant_id"], unique=False)
    op.create_index("ix_script_flows_agent_id", "script_flows", ["agent_id"], unique=False)
    op.create_index("ix_script_flows_index_status", "script_flows", ["index_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_script_flows_index_status", table_name="script_flows")
    op.drop_index("ix_script_flows_agent_id", table_name="script_flows")
    op.drop_index("ix_script_flows_tenant_id", table_name="script_flows")
    op.drop_table("script_flows")
    op.execute("DROP TYPE IF EXISTS script_flow_index_status;")
    op.execute("DROP TYPE IF EXISTS script_flow_status;")
