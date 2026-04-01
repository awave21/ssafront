"""sqns visit commodity lines

Revision ID: 0066
Revises: 0065
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sqns_visit_commodity_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visit_external_id", sa.Integer(), nullable=False),
        sa.Column("commodity_external_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=220), nullable=False),
        sa.Column("line_index", sa.Integer(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "agent_id",
            "visit_external_id",
            "source",
            "source_ref",
            "line_index",
            name="uq_sqns_vcl_agent_visit_source_ref_idx",
        ),
    )
    op.create_index("ix_sqns_visit_commodity_lines_agent_id", "sqns_visit_commodity_lines", ["agent_id"])
    op.create_index(
        "ix_sqns_visit_commodity_lines_visit_external_id",
        "sqns_visit_commodity_lines",
        ["visit_external_id"],
    )
    op.create_index(
        "ix_sqns_visit_commodity_lines_commodity_external_id",
        "sqns_visit_commodity_lines",
        ["commodity_external_id"],
    )
    op.create_index("ix_sqns_visit_commodity_lines_source", "sqns_visit_commodity_lines", ["source"])


def downgrade() -> None:
    op.drop_table("sqns_visit_commodity_lines")
