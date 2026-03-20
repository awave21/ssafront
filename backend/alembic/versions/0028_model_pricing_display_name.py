"""add display_name to model_pricing

Revision ID: 0028_model_pricing_display_name
Revises: 0027_model_pricing_and_run_costs
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0028_model_pricing_display_name"
down_revision = "0027_model_pricing_and_run_costs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_pricing", sa.Column("display_name", sa.String(length=300), nullable=True))
    op.execute("UPDATE model_pricing SET display_name = model_name WHERE display_name IS NULL")


def downgrade() -> None:
    op.drop_column("model_pricing", "display_name")
