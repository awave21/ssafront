"""Agent KG entity library (reusable Motive/Argument/Proof/... linked from ScriptNode data).

Revision ID: 0076
Revises: 0075
Create Date: 2026-04-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0076"
down_revision: Union[str, None] = "0075"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_kg_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_lc", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_id",
            "entity_type",
            "name_lc",
            name="uq_agent_kg_entity_agent_type_name",
        ),
    )
    op.create_index(
        "ix_agent_kg_entities_tenant_id",
        "agent_kg_entities",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_kg_entities_agent_id",
        "agent_kg_entities",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_kg_entities_type",
        "agent_kg_entities",
        ["agent_id", "entity_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_kg_entities_type", table_name="agent_kg_entities")
    op.drop_index("ix_agent_kg_entities_agent_id", table_name="agent_kg_entities")
    op.drop_index("ix_agent_kg_entities_tenant_id", table_name="agent_kg_entities")
    op.drop_table("agent_kg_entities")
