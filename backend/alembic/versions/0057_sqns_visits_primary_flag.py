"""add primary visit flag to sqns_visits

Revision ID: 0057
Revises: 0056
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sqns_visits",
        sa.Column("is_primary_visit", sa.Boolean(), nullable=True),
    )
    op.create_index(
        "ix_sqns_visits_is_primary_visit",
        "sqns_visits",
        ["is_primary_visit"],
        unique=False,
    )
    op.create_index(
        "ix_sqns_visits_agent_client_sort",
        "sqns_visits",
        ["agent_id", "client_external_id", "deleted", "visit_datetime", "external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sqns_visits_agent_client_sort", table_name="sqns_visits")
    op.drop_index("ix_sqns_visits_is_primary_visit", table_name="sqns_visits")
    op.drop_column("sqns_visits", "is_primary_visit")
