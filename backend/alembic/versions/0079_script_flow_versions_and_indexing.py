"""Script flow version history + indexing progress / cancel / retry.

Revision ID: 0079
Revises: 0078
Create Date: 2026-04-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0079"
down_revision: Union[str, None] = "0078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "script_flow_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("flow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("script_flows.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("flow_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("flow_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("compiled_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_script_flow_versions_flow_version",
        "script_flow_versions",
        ["flow_id", "version"],
        unique=True,
    )

    op.add_column(
        "script_flows",
        sa.Column("index_progress", sa.Integer(), nullable=True),
    )
    op.add_column(
        "script_flows",
        sa.Column("index_retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "script_flows",
        sa.Column("index_cancel_requested", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("script_flows", "index_cancel_requested")
    op.drop_column("script_flows", "index_retry_count")
    op.drop_column("script_flows", "index_progress")
    op.drop_index("ix_script_flow_versions_flow_version", table_name="script_flow_versions")
    op.drop_table("script_flow_versions")
