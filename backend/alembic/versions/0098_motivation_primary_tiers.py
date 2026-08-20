"""Split primary_pct into three tiers (low/norm/high) like repeat_pct.

Revision ID: 0098
Revises: 0097
Create Date: 2026-05-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0098"
down_revision: Union[str, None] = "0097"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "motivation_rules",
        sa.Column("primary_pct_low", sa.Numeric(5, 2), nullable=False, server_default="18.00"),
    )
    op.add_column(
        "motivation_rules",
        sa.Column("primary_pct_norm", sa.Numeric(5, 2), nullable=False, server_default="20.00"),
    )
    op.add_column(
        "motivation_rules",
        sa.Column("primary_pct_high", sa.Numeric(5, 2), nullable=False, server_default="22.00"),
    )
    # Сохраняем существующее значение primary_pct в поле _norm
    op.execute("UPDATE motivation_rules SET primary_pct_norm = primary_pct")
    op.drop_column("motivation_rules", "primary_pct")


def downgrade() -> None:
    op.add_column(
        "motivation_rules",
        sa.Column("primary_pct", sa.Numeric(5, 2), nullable=False, server_default="15.00"),
    )
    op.execute("UPDATE motivation_rules SET primary_pct = primary_pct_norm")
    op.drop_column("motivation_rules", "primary_pct_high")
    op.drop_column("motivation_rules", "primary_pct_norm")
    op.drop_column("motivation_rules", "primary_pct_low")
