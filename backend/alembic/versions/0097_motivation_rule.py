"""Add motivation_rule table for per-tenant doctor bonus settings.

Revision ID: 0097
Revises: 0096
Create Date: 2026-05-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0097"
down_revision: Union[str, None] = "0096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "motivation_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="doctor"),
        sa.Column("primary_pct", sa.Numeric(5, 2), nullable=False, server_default="15.00"),
        sa.Column("repeat_pct_low", sa.Numeric(5, 2), nullable=False, server_default="17.00"),
        sa.Column("repeat_pct_norm", sa.Numeric(5, 2), nullable=False, server_default="20.00"),
        sa.Column("repeat_pct_high", sa.Numeric(5, 2), nullable=False, server_default="22.00"),
        sa.Column("avg_check_low", sa.Numeric(12, 2), nullable=False, server_default="44000.00"),
        sa.Column("avg_check_high", sa.Numeric(12, 2), nullable=False, server_default="60000.00"),
        sa.Column("include_commodities", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("tenant_id", "role", name="uq_motivation_rule_tenant_role"),
    )
    op.create_index("ix_motivation_rules_tenant_id", "motivation_rules", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_motivation_rules_tenant_id", table_name="motivation_rules")
    op.drop_table("motivation_rules")
