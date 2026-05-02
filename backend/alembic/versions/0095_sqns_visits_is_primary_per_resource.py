"""Add is_primary_per_resource to sqns_visits.

Revision ID: 0095
Revises: 0094
Create Date: 2026-05-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0095"
down_revision: Union[str, None] = "0094"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sqns_visits",
        sa.Column("is_primary_per_resource", sa.Boolean(), nullable=True),
    )
    op.create_index(
        "ix_sqns_visits_is_primary_per_resource",
        "sqns_visits",
        ["is_primary_per_resource"],
    )


def downgrade() -> None:
    op.drop_index("ix_sqns_visits_is_primary_per_resource", table_name="sqns_visits")
    op.drop_column("sqns_visits", "is_primary_per_resource")
