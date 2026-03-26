"""add new directory template values

Revision ID: 0059
Revises: 0058
Create Date: 2026-03-25
"""

from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE directory_template ADD VALUE IF NOT EXISTS 'theme_catalog'")
    op.execute("ALTER TYPE directory_template ADD VALUE IF NOT EXISTS 'medical_course_catalog'")


def downgrade() -> None:
    # PostgreSQL enum values are not safely removable in-place.
    pass
