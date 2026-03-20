"""tenant balance and idempotent charges

Revision ID: 0055
Revises: 0054
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("initial_balance_usd", sa.Numeric(precision=18, scale=10), nullable=False, server_default=sa.text("0")),
        sa.Column("spent_usd", sa.Numeric(precision=18, scale=10), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_balances_tenant_id"),
    )
    op.create_index("ix_tenant_balances_tenant_id", "tenant_balances", ["tenant_id"], unique=False)

    op.create_table(
        "tenant_balance_charges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("amount_usd", sa.Numeric(precision=18, scale=10), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("charged_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "source_type", "source_id", name="uq_tenant_balance_charges_source"),
    )
    op.create_index("ix_tenant_balance_charges_tenant_id", "tenant_balance_charges", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tenant_balance_charges_tenant_id", table_name="tenant_balance_charges")
    op.drop_table("tenant_balance_charges")
    op.drop_index("ix_tenant_balances_tenant_id", table_name="tenant_balances")
    op.drop_table("tenant_balances")
