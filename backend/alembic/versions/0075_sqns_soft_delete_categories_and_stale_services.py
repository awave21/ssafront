"""sqns: soft-delete for categories and stale marker for services

Revision ID: 0075
Revises: 0074
Create Date: 2026-04-18

Adds:
- sqns_service_categories.deleted_at — soft-delete timestamp to preserve
  user-modified fields (is_enabled/priority) when a category disappears from SQNS.
- sqns_services.stale_since — timestamp marking services that are no longer
  returned by SQNS, so they can be hidden from UI without losing local settings.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sqns_service_categories",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_sqns_service_categories_deleted_at",
        "sqns_service_categories",
        ["deleted_at"],
    )

    op.add_column(
        "sqns_services",
        sa.Column("stale_since", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_sqns_services_stale_since",
        "sqns_services",
        ["stale_since"],
    )


def downgrade() -> None:
    op.drop_index("ix_sqns_services_stale_since", table_name="sqns_services")
    op.drop_column("sqns_services", "stale_since")

    op.drop_index(
        "ix_sqns_service_categories_deleted_at",
        table_name="sqns_service_categories",
    )
    op.drop_column("sqns_service_categories", "deleted_at")
