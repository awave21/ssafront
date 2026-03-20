"""Add active and information to sqns resources.

Revision ID: 0041
Revises: 0040
Create Date: 2026-03-12
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sqns_resources",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "sqns_resources",
        sa.Column("information", sa.Text(), nullable=True),
    )
    op.create_index(op.f("ix_sqns_resources_active"), "sqns_resources", ["active"], unique=False)
    op.alter_column("sqns_resources", "active", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_sqns_resources_active"), table_name="sqns_resources")
    op.drop_column("sqns_resources", "information")
    op.drop_column("sqns_resources", "active")
